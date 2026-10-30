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

  return {
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
      ownTrip(user, load(tripId), 'record readings for');
      if (!['start', 'end'].includes(kind)) throw new Error('kind must be start or end');
      if (typeof reading !== 'number' || !(reading >= 0)) throw new Error('reading must be a number, 0 or more');
      const trip = load(tripId);
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
      ownTrip(user, load(id), 'delete');
      const row = repos.trips.softDelete(actorId, id);
      audit(repos, actorId, 'delete', 'trips', id, null);
      return row;
    },
  };
}

module.exports = { createTripService, TRANSITIONS };
