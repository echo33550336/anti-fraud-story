/* Deterministic graph + scoring engine for the static (GitHub Pages) demo.
 * Mirrors backend/game/engine.py + scoring.py for story_frontend_graph.json. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.StaticEngine = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function getNode(config, nodeId) {
    var node = (config.nodes || []).find(function (item) { return item.id === nodeId; });
    if (!node) throw new Error('unknown node: ' + nodeId);
    return node;
  }

  function conditionMatches(condition, flags) {
    var keys = Object.keys(condition || {});
    for (var i = 0; i < keys.length; i += 1) {
      var key = keys[i];
      var expected = condition[key];
      if (key.slice(-3) === '_gt') {
        var field = key.slice(0, -3);
        var actual = flags[field] === undefined ? 0 : flags[field];
        if (typeof actual !== 'number' || actual <= expected) return false;
      } else {
        var value = flags[key] === undefined ? false : flags[key];
        if (value !== expected) return false;
      }
    }
    return true;
  }

  function optionTarget(option, flags) {
    var conditions = option.conditional_targets || [];
    for (var i = 0; i < conditions.length; i += 1) {
      if (conditionMatches(conditions[i].when || {}, flags)) {
        return conditions[i].target;
      }
    }
    return option.target;
  }

  function applyChoice(config, flags, nodeId, optionId) {
    var node = getNode(config, nodeId);
    var option = (node.options || []).find(function (item) { return item.id === optionId; });
    if (!option) throw new Error('invalid option for ' + nodeId + ': ' + optionId);
    var updated = Object.assign({}, flags);
    updated[nodeId.toLowerCase()] = optionId;
    var optionFlags = option.flags || {};
    Object.keys(optionFlags).forEach(function (key) { updated[key] = optionFlags[key]; });
    var increments = option.increments || {};
    Object.keys(increments).forEach(function (key) {
      var current = updated[key] === undefined ? 0 : updated[key];
      if (typeof current !== 'number') throw new Error(key + ' must be a number');
      updated[key] = current + increments[key];
    });
    return { flags: updated, target: optionTarget(option, updated), response: option.response || '' };
  }

  function applyFreeAnswer(config, flags, nodeId, text) {
    var node = getNode(config, nodeId);
    if (!node.free) throw new Error('node does not accept a free answer');
    var spec = node.free_answer || {};
    var raw = String(text || '').trim();
    if (raw.length < (spec.min_length || 1)) return null;
    var normalized = raw.toLowerCase();
    var routes = spec.routes || [];
    for (var i = 0; i < routes.length; i += 1) {
      var route = routes[i];
      var any = route.any_keywords || [];
      var all = route.all_keywords || [];
      var none = route.none_keywords || [];
      if (any.length && !any.some(function (word) { return normalized.indexOf(String(word).toLowerCase()) !== -1; })) continue;
      if (all.length && !all.every(function (word) { return normalized.indexOf(String(word).toLowerCase()) !== -1; })) continue;
      if (none.some(function (word) { return normalized.indexOf(String(word).toLowerCase()) !== -1; })) continue;
      var updated = Object.assign({}, flags);
      Object.assign(updated, route.set_flags || {});
      updated[nodeId.toLowerCase()] = route.target;
      return { flags: updated, target: route.target, route: route };
    }
    return null;
  }

  function totalPaid(flags, fields) {
    return (fields || []).reduce(function (sum, key) { return sum + (flags[key] || 0); }, 0);
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function buildReview(config, flags, endingId, history) {
    var ending = (config.endings || []).find(function (item) { return item.id === endingId; });
    if (!ending) throw new Error('unknown ending: ' + endingId);
    var spec = config.scoring;
    var paid = totalPaid(flags, spec.payment_fields);
    var score = 100 - Math.min(spec.max_payment_deduction, Math.floor(paid / 100));
    score -= spec.ending_penalties[endingId] || 0;
    score = Math.max(score, spec.minimum_score_by_ending[endingId] === undefined
      ? spec.score_min
      : spec.minimum_score_by_ending[endingId]);
    score = clamp(score, spec.score_min, spec.score_max);

    var badges = (spec.badges || []).filter(function (badge) {
      var earned = (badge.any_flags || []).some(function (key) { return flags[key] === true; });
      earned = earned || (badge.any_endings || []).indexOf(endingId) !== -1;
      earned = earned || (badge.any_paid_fields || []).some(function (key) { return (flags[key] || 0) > 0; });
      return earned;
    }).map(function (badge) { return badge.name; });

    var paidDetail = {};
    (spec.payment_fields || []).forEach(function (key) { paidDetail[key] = flags[key] || 0; });

    return {
      ending_id: endingId,
      title: ending.title,
      rating: ending.rating,
      narration: ending.narration,
      note: ending.note,
      score: score,
      badges: badges,
      paid: paidDetail,
      total_paid: paid,
      history: (history || []).slice()
    };
  }

  return {
    getNode: getNode,
    conditionMatches: conditionMatches,
    optionTarget: optionTarget,
    applyChoice: applyChoice,
    applyFreeAnswer: applyFreeAnswer,
    totalPaid: totalPaid,
    buildReview: buildReview
  };
});
