import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
  timeout: 10000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail ?? error.response?.data?.message;
    if (typeof detail === "string" && detail) {
      return Promise.reject(new Error(detail));
    }
    return Promise.reject(error);
  },
);
