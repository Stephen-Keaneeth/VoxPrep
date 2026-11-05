import { create } from "zustand";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  description?: string;
  duration?: number;
}

interface ToastState {
  toasts: ToastItem[];
  addToast: (toast: Omit<ToastItem, "id">) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    const duration = toast.duration ?? 4000;

    set((state) => ({
      toasts: [...state.toasts.slice(-4), { ...toast, id }],
    }));

    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, duration);
    }
  },
  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));

export const toast = {
  success: (message: string, description?: string) =>
    useToastStore.getState().addToast({ type: "success", message, description }),
  error: (message: string, description?: string) =>
    useToastStore.getState().addToast({ type: "error", message, description }),
  info: (message: string, description?: string) =>
    useToastStore.getState().addToast({ type: "info", message, description }),
  warning: (message: string, description?: string) =>
    useToastStore.getState().addToast({ type: "warning", message, description }),
};

