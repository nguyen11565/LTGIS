require("dotenv").config();
const { createApp } = require("./app");
const { createMemoryStore } = require("./storage/memory");
const { createDemoState } = require("./seedData");
(async () => {
  const store = createMemoryStore(await createDemoState());
  const app = createApp({
    store,
    jwtSecret: "explicit-demo-only-secret-no-real-data-2026",
  });
  const port = Number(process.env.PORT || 5000);
  app.listen(port, "0.0.0.0", () =>
    console.log(
      `DEMO ONLY: API on ${port}, IN-MEMORY data resets on restart; payments SIMULATED.`,
    ),
  );
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
