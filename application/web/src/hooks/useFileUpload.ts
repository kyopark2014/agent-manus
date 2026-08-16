import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { fileUploadService } from "../services/fileUploadService";

export interface AttachedImage {
  url: string;
  name: string;
  previewUrl: string;
}

const ERROR_MESSAGE_DISPLAY_DURATION_MS = 5000;

function extensionFromMime(mime: string): string {
  if (mime === "image/jpeg") return ".jpg";
  if (mime === "image/webp") return ".webp";
  if (mime === "image/gif") return ".gif";
  return ".png";
}

export function isImageFile(file: File): boolean {
  if (file.type.startsWith("image/")) return true;
  return /\.(png|jpe?g|gif|webp)$/i.test(file.name);
}

export function normalizeImageFile(
  file: File,
  fallbackName = "pasted_screenshot",
): File {
  if (!isImageFile(file)) return file;
  const mime = file.type || "image/png";
  const ext = extensionFromMime(mime);
  const hasUsefulName =
    file.name &&
    file.name !== "image.png" &&
    file.name !== "image.jpg" &&
    file.name !== "blob";
  if (hasUsefulName) return file;
  return new File([file], `${fallbackName}${ext}`, { type: mime });
}

export function collectClipboardImages(clipboardData: DataTransfer | null): File[] {
  if (!clipboardData) return [];

  const files: File[] = [];
  const seen = new Set<string>();

  // Clipboard File objects for the same paste often differ in name/lastModified
  // between items and files, so dedupe by size+type only.
  const pushUnique = (file: File) => {
    const key = `${file.size}:${file.type || "image/png"}`;
    if (seen.has(key)) return;
    seen.add(key);
    files.push(normalizeImageFile(file));
  };

  // Prefer items; files usually mirrors the same image with different metadata.
  for (const item of Array.from(clipboardData.items ?? [])) {
    if (!item.type.startsWith("image/")) continue;
    const blob = item.getAsFile();
    if (blob) pushUnique(blob);
  }

  if (files.length === 0) {
    for (const file of Array.from(clipboardData.files ?? [])) {
      if (isImageFile(file)) pushUnique(file);
    }
  }

  return files;
}

interface UseFileUploadOptions {
  disabled?: boolean;
}

export function useFileUpload({ disabled = false }: UseFileUploadOptions = {}) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<AttachedImage[]>([]);
  const attachmentsRef = useRef<AttachedImage[]>([]);
  const uploadingRef = useRef(false);

  attachmentsRef.current = attachments;
  uploadingRef.current = uploading;

  useEffect(() => {
    if (!uploadError) return;
    const timer = window.setTimeout(
      () => setUploadError(null),
      ERROR_MESSAGE_DISPLAY_DURATION_MS,
    );
    return () => window.clearTimeout(timer);
  }, [uploadError]);

  useEffect(() => {
    return () => {
      for (const item of attachmentsRef.current) {
        if (item.previewUrl.startsWith("blob:")) {
          URL.revokeObjectURL(item.previewUrl);
        }
      }
    };
  }, []);

  const clearUploadError = useCallback(() => setUploadError(null), []);

  const uploadImageFile = useCallback(async (file: File) => {
    setUploading(true);
    setUploadError(null);
    const previewUrl = URL.createObjectURL(file);
    try {
      const result = await fileUploadService.uploadImage(file);
      setAttachments((prev) => [
        ...prev,
        {
          url: result.url,
          name: result.file_name,
          previewUrl,
        },
      ]);
    } catch (err) {
      URL.revokeObjectURL(previewUrl);
      console.error("Image upload failed", err);
      setUploadError("이미지 업로드에 실패했습니다. 다시 시도해 주세요.");
    } finally {
      setUploading(false);
    }
  }, []);

  const uploadImageFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0 || disabled || uploadingRef.current) return;
      for (const file of files) {
        await uploadImageFile(normalizeImageFile(file, "uploaded_image"));
      }
    },
    [disabled, uploadImageFile],
  );

  const uploadRagFile = useCallback(
    async (file: File, onComplete?: (message: string) => void) => {
      if (disabled || uploadingRef.current) return;
      setUploading(true);
      setUploadError(null);
      try {
        const result = await fileUploadService.uploadToRag(file);
        onComplete?.(result.message);
      } catch (err) {
        console.error("Document upload failed", err);
        setUploadError("파일 업로드에 실패했습니다. 다시 시도해 주세요.");
      } finally {
        setUploading(false);
      }
    },
    [disabled],
  );

  const removeAttachment = useCallback((url: string) => {
    setAttachments((prev) => {
      const next: AttachedImage[] = [];
      for (const item of prev) {
        if (item.url === url) {
          if (item.previewUrl.startsWith("blob:")) {
            URL.revokeObjectURL(item.previewUrl);
          }
          continue;
        }
        next.push(item);
      }
      return next;
    });
  }, []);

  const clearAttachments = useCallback(() => {
    setAttachments((prev) => {
      for (const item of prev) {
        if (item.previewUrl.startsWith("blob:")) {
          URL.revokeObjectURL(item.previewUrl);
        }
      }
      return [];
    });
  }, []);

  const [dragOver, setDragOver] = useState(false);
  const dragDepthRef = useRef(0);

  const onDragEnter = useCallback(
    (e: DragEvent) => {
      if (disabled || uploadingRef.current) return;
      if (![...e.dataTransfer.types].includes("Files")) return;
      e.preventDefault();
      dragDepthRef.current += 1;
      setDragOver(true);
    },
    [disabled],
  );

  const onDragOver = useCallback(
    (e: DragEvent) => {
      if (disabled || uploadingRef.current) return;
      if (![...e.dataTransfer.types].includes("Files")) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    },
    [disabled],
  );

  const onDragLeave = useCallback((e: DragEvent) => {
    if (![...e.dataTransfer.types].includes("Files") && dragDepthRef.current === 0) {
      return;
    }
    e.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setDragOver(false);
  }, []);

  const onDrop = useCallback(
    async (e: DragEvent) => {
      e.preventDefault();
      dragDepthRef.current = 0;
      setDragOver(false);
      if (disabled || uploadingRef.current) return;
      const imageFiles = Array.from(e.dataTransfer.files ?? []).filter(isImageFile);
      await uploadImageFiles(imageFiles);
    },
    [disabled, uploadImageFiles],
  );

  return {
    uploading,
    uploadError,
    attachments,
    dragOver,
    isUploading: () => uploadingRef.current,
    clearUploadError,
    uploadImageFiles,
    uploadRagFile,
    removeAttachment,
    clearAttachments,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
  };
}
