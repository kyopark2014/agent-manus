import { api } from "../api";

/** Normalize any thrown value into an Error with a useful user-facing message. */
function toUploadError(context: string, cause: unknown): Error {
  let detail = "";
  if (cause instanceof Error && cause.message.trim()) {
    detail = cause.message.trim();
  } else if (typeof cause === "string" && cause.trim()) {
    detail = cause.trim();
  }
  const message = detail && detail !== context ? `${context}: ${detail}` : context;
  const error = new Error(message);
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

  async uploadToRag(
    file: File,
    options?: { sync?: boolean },
  ): Promise<{ message: string; file_name: string }> {
    try {
      const result = await api.uploadToRag(file, options);
      return { message: result.message, file_name: result.file_name };
    } catch (cause) {
      throw toUploadError("RAG upload failed", cause);
    }
  },
};
