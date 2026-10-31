require("dotenv").config();
const { connectStore } = require("./storage/sql");
const { createApp } = require("./app");
async function start() {
  if (!process.env.JWT_SECRET || process.env.JWT_SECRET.length < 24)
    throw Error(
      "JWT_SECRET phải có ít nhất 24 ký tự. Tạo .env từ .env.example và đặt bí mật riêng.",
    );
  const store = await connectStore();
  await store.health();
  const app = createApp({ store, jwtSecret: process.env.JWT_SECRET });
  const port = Number(process.env.PORT || 5000),
    server = app.listen(port, "0.0.0.0", () =>
      console.log(
        `API sẵn sàng trên cổng ${port}; SQL Server đã kết nối; thanh toán MÔ PHỎNG.`,
      ),
    );
  for (const signal of ["SIGINT", "SIGTERM"])
    process.on(signal, () => {
      server.close(async () => {
        await store.close();
        process.exit(0);
      });
    });
}
start().catch((error) => {
  console.error("Không khởi động được API:", error.message);
  process.exit(1);
});
