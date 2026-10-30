// Role check done on the server side of every call; the UI is not trusted.
const ROLES = ['requestor', 'driver', 'supervisor', 'accounting', 'admin'];

function requireRole(repos, actorId, allowed, what) {
  const user = repos.users.get(actorId);
  if (!user) throw new Error(`unknown user ${actorId}`);
  if (user.role !== 'admin' && !allowed.includes(user.role)) {
    throw new Error(`role ${user.role} is not allowed to ${what}`);
  }
  return user;
}

module.exports = { ROLES, requireRole };
