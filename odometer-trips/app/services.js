// Services: business rules for vehicles (M1) and trips (M2). No storage access here.

export const FUEL_TYPES = ['Gasoline', 'Diesel', 'Electric', 'Hybrid', 'Other'];
const PURPOSE_GROUP = 'trip_purpose';

export class ValidationError extends Error {
  constructor(field, message) {
    super(message);
    this.name = 'ValidationError';
    this.field = field;
  }
}

function text(value, field, label, max = 80) {
  const s = String(value ?? '').trim();
  if (!s) throw new ValidationError(field, `${label} is required.`);
  if (s.length > max) throw new ValidationError(field, `${label} must be ${max} characters or fewer.`);
  return s;
}

function wholeKm(value, field, label) {
  if (value === null || value === undefined || String(value).trim() === '') {
    throw new ValidationError(field, `${label} is required.`);
  }
  const s = String(value).trim();
  if (!/^\d+$/.test(s)) throw new ValidationError(field, `${label} must be a whole number of km, 0 or more.`);
  const n = Number(s);
  if (!Number.isSafeInteger(n)) throw new ValidationError(field, `${label} is too large.`);
  return n;
}

function isoDate(value, field) {
  const s = String(value ?? '').trim();
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  const d = m && new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  if (!m || d.getUTCFullYear() !== +m[1] || d.getUTCMonth() !== +m[2] - 1 || d.getUTCDate() !== +m[3]) {
    throw new ValidationError(field, 'Date must be a real date in yyyy-mm-dd format.');
  }
  return s;
}

export function distanceKm(trip) {
  return trip.end_km - trip.start_km;
}

export function createServices(repo) {
  function activeVehicle(id) {
    const v = id ? repo.get('vehicles', id) : null;
    if (!v || !v.is_active) throw new ValidationError('vehicle_id', 'Choose an active vehicle.');
    return v;
  }

  function lastEndKm(vehicleId) {
    const v = repo.get('vehicles', vehicleId);
    if (!v) throw new ValidationError('vehicle_id', 'Vehicle not found.');
    return repo
      .list('trips')
      .filter((t) => t.vehicle_id === vehicleId && t.status === 'Closed')
      .reduce((max, t) => Math.max(max, t.end_km), v.start_odometer_km);
  }

  function listPurposes() {
    return repo
      .list('lookups')
      .filter((r) => r.group_name === PURPOSE_GROUP)
      .map((r) => ({ id: r.id, value: r.value }));
  }

  return {
    listVehicles({ includeInactive = false } = {}) {
      return repo.list('vehicles', { includeInactive });
    },

    addVehicle(input = {}) {
      const name = text(input.name, 'name', 'Vehicle name');
      const plate = text(input.plate, 'plate', 'Plate', 20).toUpperCase();
      const fuel_type = String(input.fuel_type ?? '').trim();
      if (!FUEL_TYPES.includes(fuel_type)) {
        throw new ValidationError('fuel_type', `Fuel type must be one of: ${FUEL_TYPES.join(', ')}.`);
      }
      const start_odometer_km = wholeKm(input.start_odometer_km, 'start_odometer_km', 'Starting odometer');
      if (repo.list('vehicles').some((v) => v.plate === plate)) {
        throw new ValidationError('plate', `A vehicle with plate ${plate} already exists.`);
      }
      return repo.insert('vehicles', { name, plate, fuel_type, start_odometer_km });
    },

    voidVehicle(id) {
      const v = repo.get('vehicles', id);
      if (!v) throw new ValidationError('id', 'Vehicle not found.');
      if (!v.is_active) throw new ValidationError('id', 'This vehicle is already voided.');
      return repo.softDelete('vehicles', id);
    },

    listPurposes,
    lastEndKm,

    addTrip(input = {}) {
      const vehicle = activeVehicle(input.vehicle_id);
      const trip_date = isoDate(input.trip_date, 'trip_date');
      const start_km = wholeKm(input.start_km, 'start_km', 'Start reading');
      const end_km = wholeKm(input.end_km, 'end_km', 'End reading');
      const purpose = listPurposes().find((p) => p.id === input.purpose_id);
      if (!purpose) throw new ValidationError('purpose_id', 'Choose a trip purpose.');
      const destination = text(input.destination, 'destination', 'Destination', 120);

      const last = lastEndKm(vehicle.id);
      if (start_km < last) {
        throw new ValidationError(
          'start_km',
          `Start reading (${start_km} km) is below this vehicle's last end reading (${last} km).`,
        );
      }
      if (end_km < start_km) {
        throw new ValidationError('end_km', `End reading (${end_km} km) is below the start reading (${start_km} km).`);
      }
      return repo.insert('trips', {
        vehicle_id: vehicle.id, trip_date, start_km, end_km, purpose_id: purpose.id, destination, status: 'Closed',
      });
    },

    // Distance, vehicle name and purpose are added for display only; none are stored.
    listTrips() {
      const vehicles = new Map(repo.list('vehicles', { includeInactive: true }).map((v) => [v.id, v]));
      const purposes = new Map(repo.list('lookups', { includeInactive: true }).map((p) => [p.id, p.value]));
      return repo
        .list('trips', { includeInactive: true })
        .sort((a, b) => (a.trip_date === b.trip_date ? b.id.localeCompare(a.id) : b.trip_date.localeCompare(a.trip_date)))
        .map((t) => ({
          ...t,
          distance_km: distanceKm(t),
          vehicle_name: vehicles.get(t.vehicle_id)?.name ?? t.vehicle_id,
          purpose: purposes.get(t.purpose_id) ?? '',
        }));
    },

    voidTrip(id) {
      const t = repo.get('trips', id);
      if (!t) throw new ValidationError('id', 'Trip not found.');
      if (!t.is_active) throw new ValidationError('id', 'This trip is already voided.');
      return repo.softDelete('trips', id, { status: 'Voided' });
    },
  };
}
