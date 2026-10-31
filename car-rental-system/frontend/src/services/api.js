export const API_BASE = (import.meta.env.VITE_API_URL || "/api").replace(
  /\/$/,
  "",
);
export function getToken() {
  return localStorage.getItem("lai-viet-token");
}
export async function request(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new Error(
      "Không thể kết nối máy chủ. Vui lòng kiểm tra backend và thử lại.",
    );
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) {
    const error = new Error(
      payload?.message || `Yêu cầu thất bại (${response.status}).`,
    );
    error.status = response.status;
    error.data = payload?.data;
    throw error;
  }
  return payload?.data ?? payload;
}
export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  put: (path, body) => request(path, { method: "PUT", body }),
  delete: (path) => request(path, { method: "DELETE" }),
};
export function asList(data) {
  return Array.isArray(data)
    ? data
    : data?.items ||
        data?.cars ||
        data?.orders ||
        data?.notifications ||
        data?.logs ||
        data?.users ||
        [];
}
export async function openContract(id) {
  const popup = window.open("", "_blank");
  if (!popup) throw new Error("Vui lòng cho phép mở cửa sổ để xem hợp đồng.");
  popup.document.write(
    '<p style="font-family:system-ui;padding:32px">Đang tải hợp đồng…</p>',
  );
  try {
    const res = await fetch(`${API_BASE}/orders/${id}/contract`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.message || "Chưa có hợp đồng cho đơn này.");
    }
    const html = await res.text();
    popup.document.open();
    popup.document.write(html);
    popup.document.close();
  } catch (error) {
    popup.close();
    throw error;
  }
}
