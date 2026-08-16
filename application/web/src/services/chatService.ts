import { api } from "../api";

/** Service layer for chat streaming — keeps hooks free of direct API calls. */
export const chatService = {
  streamChat(
    taskId: string,
    prompt: string,
    files: string[] = [],
    signal?: AbortSignal,
  ) {
    return api.streamChat(taskId, prompt, files, signal);
  },
};
