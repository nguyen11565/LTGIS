// Explicit test adapter only. Production server never imports this module.
const TABLES = [
  "Users",
  "Cars",
  "RentalOrders",
  "Payments",
  "Contracts",
  "Notifications",
  "AuditLogs",
  "VehicleHandovers",
  "VehicleReturns",
  "ExtraFees",
];
function createMemoryStore(initial = {}) {
  let state = Object.fromEntries(
    TABLES.map((t) => [t, structuredClone(initial[t] || [])]),
  );
  let queue = Promise.resolve();
  const context = (data) => ({
    async list(t) {
      return structuredClone(data[t]);
    },
    async get(t, id) {
      return structuredClone(data[t].find((r) => r.Id === Number(id)));
    },
    async insert(t, values) {
      const row = {
        ...structuredClone(values),
        Id: Math.max(0, ...data[t].map((r) => r.Id)) + 1,
      };
      data[t].push(row);
      return structuredClone(row);
    },
    async update(t, id, values) {
      const row = data[t].find((r) => r.Id === Number(id));
      if (!row) return undefined;
      Object.assign(row, structuredClone(values));
      return structuredClone(row);
    },
  });
  return {
    kind: "memory",
    list: (t) => context(state).list(t),
    get: (t, id) => context(state).get(t, id),
    async transaction(fn) {
      const result = queue.then(async () => {
        const draft = structuredClone(state);
        const value = await fn(context(draft));
        state = draft;
        return value;
      });
      queue = result.catch(() => {});
      return result;
    },
    async health() {
      return true;
    },
    async close() {},
    snapshot: () => structuredClone(state),
  };
}
module.exports = { createMemoryStore };
