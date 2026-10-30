// audit_log is append-only: the service only ever inserts into it.
function audit(repos, actorId, action, table, recordId, detail) {
  return repos.audit_log.insert(actorId, {
    at: repos.now(),
    actor_id: actorId,
    action,
    table,
    record_id: recordId,
    detail: detail == null ? null : String(detail),
  });
}

module.exports = { audit };
