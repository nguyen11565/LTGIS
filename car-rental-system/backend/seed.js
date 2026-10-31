require("dotenv").config();
const { connectStore } = require("./storage/sql");
const { createDemoState } = require("./seedData");
async function main() {
  if (
    process.env.NODE_ENV === "production" &&
    process.env.ALLOW_DEMO_SEED !== "true"
  )
    throw Error(
      "Demo seed bị tắt trong production. Chỉ bật ALLOW_DEMO_SEED=true khi chủ động tạo dữ liệu demo.",
    );
  const store = await connectStore();
  try {
    const state = await createDemoState();
    await store.transaction(async (ctx) => {
      const users = await ctx.list("Users");
      for (const { Id, ...u } of state.Users) {
        if (
          !users.some(
            (x) =>
              x.Username.toLowerCase() === u.Username ||
              x.Email.toLowerCase() === u.Email,
          )
        )
          await ctx.insert("Users", u);
      }
      const cars = await ctx.list("Cars");
      for (const { Id, ...c } of state.Cars) {
        if (!cars.some((x) => x.LicensePlate === c.LicensePlate))
          await ctx.insert("Cars", c);
      }
    });
    console.log(
      "Demo seed complete (existing users/cars preserved). admin/Admin@123 employee/Employee@123 customer/Customer@123",
    );
  } finally {
    await store.close();
  }
}
main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
