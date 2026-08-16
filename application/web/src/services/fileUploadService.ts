import { api } from "../api";

/** Normalize any thrown value into an Error with a safe, user-facing message. */
function toUploadError(context: string, cause: unknown): Error {
  // Never forward raw exception text (stack fragments, SDK internals) to the UI.
  const error = new Error(context);
  if (cause instanceof Error) {
    (error as Error & { cause?: unknown }).cause = cause;
  }
  return error;
}

/** Service layer for file uploads — keeps hooks free of direct API calls. */
export const fileUploadService = {
  async uploadImage(file: File): Promise<{ url: string; file_name: string }> {
    try {
      return await api.uploadFile(file);
    } catch (cause) {
      throw toUploadError("Image upload failed", cause);
    }
  },

  async uploadToRag(file: File): Promise<{ message: string }> {
    try {
      return await api.uploadToRag(file);
    } catch (cause) {
      throw toUploadError("RAG upload failed", cause);
    }
  },
};
