const { requireRole } = require('./access');
const { audit } = require('./audit');

// The status flow lives in this one table.
const TRANSITIONS = {
  Draft: ['Submitted'],
  Submitted: ['Trip validated', 'Draft'],
  'Trip validated': ['Completed', 'Draft'],
  Completed: [],
};
const WHO = {
  create: ['requestor', 'driver'],
  submit: ['requestor', 'driver'],
  validate: ['supervisor'],
  complete: ['accounting'],
  returnToDraft: ['supervisor'],
};
const SEES_ALL = ['supervisor', 'accounting', 'admin'];

function createTripService(repos) {
  function load(id) {
    const trip = repos.trips.get(id);
    if (!trip) throw new Error(`trip ${id} not found`);
    return trip;
  }
  function ownTrip(user, trip, what) {
    if (user.role !== 'admin' && trip.requestor_id !== user.id) {
      throw new Error(`only the requestor may ${what} their own trips`);
    }
  }
  // The flow table is checked first, so a wrong status always reports an illegal transition.
  function assertCanMove(id, to) {
    const trip = load(id);
    if (!TRANSITIONS[trip.status].includes(to)) {
      throw new Error(`illegal transition ${trip.status} to ${to}`);
    }
    return trip;
  }
  function move(actorId, id, to, action, detail) {
    const trip = assertCanMove(id, to);
    const updated = repos.trips.update(actorId, id, Object.assign({ status: to }, detail ? { note: detail } : {}));
    audit(repos, actorId, action, 'trips', id, `${trip.status} to ${to}`);
    return updated;
  }
  function readings(tripId) {
    return repos.vehicle_readings.list({ where: { trip_id: tripId } });
  }

  function canSee(user, trip) {
    return SEES_ALL.includes(user.role) || trip.requestor_id === user.id;
  }
  function knownUser(actorId) {
    const user = repos.users.get(actorId);
    if (!user) throw new Error(`unknown user ${actorId}`);
    return user;
  }

  return {
    // Requestors and drivers see their own trips; supervisor, accounting and admin see all.
    listTrips(actorId, filter) {
      const user = knownUser(actorId);
      const where = filter && filter.status ? { status: filter.status } : {};
      return repos.trips.list({ where, limit: 1000 }).filter((t) => canSee(user, t));
    },
    getTrip(actorId, id) {
      const user = knownUser(actorId);
      const trip = load(id);
      if (!canSee(user, trip)) throw new Error('you may not view this trip');
      return Object.assign({}, trip, {
        travellers: repos.trip_travellers.list({ where: { trip_id: id } }),
        readings: readings(id),
      });
    },
    // Dummy-safe lookups for the form drop-downs.
    lookups(actorId) {
      knownUser(actorId);
      return { vehicles: repos.vehicles.list(), teams: repos.teams.list(), users: repos.users.list() };
    },
    updateTrip(actorId, id, input) {
      const user = requireRole(repos, actorId, WHO.create, 'edit a trip');
      const trip = load(id);
      ownTrip(user, trip, 'edit');
      if (trip.status !== 'Draft') throw new Error('only a Draft trip can be edited');
      const changes = {};
      for (const f of ['vehicle_id', 'team_id', 'purpose', 'note']) {
        if (f in input) changes[f] = input[f];
      }
      for (const f of ['vehicle_id', 'team_id', 'purpose']) {
        if (f in changes && !changes[f]) throw new Error(`${f === 'vehicle_id' ? 'vehicle' : f} is required`);
      }
      if (changes.vehicle_id && !repos.vehicles.get(changes.vehicle_id)) throw new Error(`vehicle ${changes.vehicle_id} not found`);
      if (changes.team_id && !repos.teams.get(changes.team_id)) throw new Error(`team ${changes.team_id} not found`);
      const updated = repos.trips.update(actorId, id, changes);
      audit(repos, actorId, 'update', 'trips', id, Object.keys(changes).join(','));
      return updated;
    },
    createTrip(actorId, input) {
      const user = requireRole(repos, actorId, WHO.create, 'create a trip');
      for (const f of ['vehicle_id', 'team_id', 'purpose']) {
        if (!input[f]) throw new Error(`${f === 'vehicle_id' ? 'vehicle' : f} is required`);
      }
      if (!repos.vehicles.get(input.vehicle_id)) throw new Error(`vehicle ${input.vehicle_id} not found`);
      if (!repos.teams.get(input.team_id)) throw new Error(`team ${input.team_id} not found`);
      const trip = repos.trips.insert(actorId, {
        status: 'Draft', requestor_id: user.id, vehicle_id: input.vehicle_id,
        team_id: input.team_id, purpose: input.purpose, note: input.note || null,
      });
      audit(repos, actorId, 'create', 'trips', trip.id, null);
      return trip;
    },
    addTraveller(actorId, tripId, userId) {
      const user = requireRole(repos, actorId, WHO.create, 'add a traveller');
      const trip = load(tripId);
      ownTrip(user, trip, 'add travellers to');
      if (trip.status !== 'Draft') throw new Error('travellers can only change while the trip is Draft');
      if (!repos.users.get(userId)) throw new Error(`unknown user ${userId}`);
      const row = repos.trip_travellers.insert(actorId, { trip_id: tripId, user_id: userId });
      audit(repos, actorId, 'add_traveller', 'trip_travellers', row.id, userId);
      return row;
    },
    recordReading(actorId, tripId, kind, reading) {
      const user = requireRole(repos, actorId, WHO.create, 'record a reading');
      const trip = load(tripId);
      ownTrip(user, trip, 'record readings for');
      if (trip.status !== 'Draft') throw new Error('readings can only change while the trip is Draft');
      if (!['start', 'end'].includes(kind)) throw new Error('kind must be start or end');
      if (typeof reading !== 'number' || !(reading >= 0)) throw new Error('reading must be a number, 0 or more');
      if (readings(tripId).some((r) => r.kind === kind)) throw new Error(`a ${kind} reading already exists for this trip`);
      const row = repos.vehicle_readings.insert(actorId, { trip_id: tripId, vehicle_id: trip.vehicle_id, kind, reading });
      audit(repos, actorId, 'record_reading', 'vehicle_readings', row.id, kind);
      return row;
    },
    submit(actorId, id) {
      const user = requireRole(repos, actorId, WHO.submit, 'submit a trip');
      ownTrip(user, load(id), 'submit');
      return move(actorId, id, 'Submitted', 'submit');
    },
    validate(actorId, id) {
      requireRole(repos, actorId, WHO.validate, 'validate a trip');
      assertCanMove(id, 'Trip validated');
      if (!repos.trip_travellers.list({ where: { trip_id: id } }).length) {
        throw new Error('a trip needs at least one traveller to be validated');
      }
      return move(actorId, id, 'Trip validated', 'validate');
    },
    complete(actorId, id) {
      requireRole(repos, actorId, WHO.complete, 'complete a trip');
      assertCanMove(id, 'Completed');
      const rs = readings(id);
      const start = rs.find((r) => r.kind === 'start');
      const end = rs.find((r) => r.kind === 'end');
      if (!start || !end) throw new Error('start and end readings are required to complete');
      if (end.reading < start.reading) throw new Error('end reading cannot be below the start reading');
      return move(actorId, id, 'Completed', 'complete');
    },
    returnToDraft(actorId, id, reason) {
      requireRole(repos, actorId, WHO.returnToDraft, 'return a trip to Draft');
      if (!reason) throw new Error('a reason is required to return a trip to Draft');
      return move(actorId, id, 'Draft', 'return_to_draft', reason);
    },
    deleteTrip(actorId, id) {
      const user = requireRole(repos, actorId, WHO.create, 'delete a trip');
      const trip = load(id);
      ownTrip(user, trip, 'delete');
      if (trip.status !== 'Draft') throw new Error('only a Draft trip can be deleted');
      const row = repos.trips.softDelete(actorId, id);
      audit(repos, actorId, 'delete', 'trips', id, null);
      return row;
    },
  };
}

module.exports = { createTripService, TRANSITIONS };
