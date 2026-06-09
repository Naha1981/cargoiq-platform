"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import {
  Upload, File, X, CheckCircle,
  AlertCircle, ArrowLeft, Loader2
} from "lucide-react";
import { documentsApi, shipmentsApi } from "@/lib/api";
import { TopNav } from "@/components/layout/TopNav";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

interface UploadedFile {
  file: File;
  id?: string;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
  docType?: string;
}

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles]           = useState<UploadedFile[]>([]);
  const [processing, setProcessing] = useState(false);

  const onDrop = useCallback((accepted: File[]) => {
    setFiles(prev => [
      ...prev,
      ...accepted.map(f => ({ file: f, status: "pending" as const }))
    ]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf":  [".pdf"],
      "image/jpeg":       [".jpg", ".jpeg"],
      "image/png":        [".png"],
      "image/tiff":       [".tiff", ".tif"],
    },
    maxSize: 50 * 1024 * 1024,
    multiple: true,
  });

  const removeFile = (idx: number) =>
    setFiles(prev => prev.filter((_, i) => i !== idx));

  const uploadAll = async () => {
    const pending = files.filter(f => f.status === "pending");
    if (!pending.length) return;

    setProcessing(true);
    const uploadedIds: string[] = [];

    for (let i = 0; i < files.length; i++) {
      if (files[i].status !== "pending") {
        if (files[i].id) uploadedIds.push(files[i].id!);
        continue;
      }

      setFiles(prev => prev.map((f, idx) =>
        idx === i ? { ...f, status: "uploading" } : f
      ));

      try {
        const res = await documentsApi.upload(files[i].file);
        uploadedIds.push(res.id);
        setFiles(prev => prev.map((f, idx) =>
          idx === i ? { ...f, status: "done", id: res.id, docType: res.doc_type } : f
        ));
      } catch (err: any) {
        setFiles(prev => prev.map((f, idx) =>
          idx === i ? { ...f, status: "error", error: err.message } : f
        ));
      }
    }

    if (uploadedIds.length > 0) {
      try {
        // Wait 3s for OCR to start
        await new Promise(r => setTimeout(r, 3000));

        const shipment = await shipmentsApi.createFromDocuments(uploadedIds);
        toast.success("Shipment created — extraction pipeline started");
        router.push(`/shipments/${shipment.shipment_id}`);
      } catch (err: any) {
        // OCR might still be running — navigate to queue
        toast.success("Documents uploaded. Processing in background.");
        router.push("/queue");
      }
    }

    setProcessing(false);
  };

  const allDone = files.length > 0 && files.every(f => f.status !== "error");
  const hasErrors = files.some(f => f.status === "error");

  return (
    <div className="flex flex-col min-h-full">
      <TopNav breadcrumbs={[
        { label: "Queue", href: "/queue" },
        { label: "Upload Documents" }
      ]} />

      <div className="p-6 max-w-2xl">
        <div className="flex items-center gap-3 mb-6">
          <button className="btn btn-ghost btn-sm p-1.5" onClick={() => router.back()}>
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-xl font-semibold text-text-primary">Upload Freight Documents</h1>
            <p className="text-xs text-text-tertiary mt-0.5">
              Upload your commercial invoice and packing list together for cross-reference validation
            </p>
          </div>
        </div>

        {/* Drop zone */}
        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors duration-150 mb-5",
            isDragActive
              ? "border-accent bg-accent/5"
              : "border-border hover:border-accent/50 hover:bg-subtle"
          )}
        >
          <input {...getInputProps()} />
          <Upload className={cn(
            "w-10 h-10 mx-auto mb-3 stroke-[1.5]",
            isDragActive ? "text-accent" : "text-text-tertiary"
          )} />
          <p className="text-sm font-medium text-text-primary mb-1">
            {isDragActive ? "Drop files here" : "Drag & drop freight documents"}
          </p>
          <p className="text-xs text-text-tertiary">
            PDF, JPEG, PNG, TIFF · Max 50MB per file · Multiple files supported
          </p>
          <button className="btn btn-secondary btn-sm mt-4">Browse Files</button>
        </div>

        {/* Recommended combination */}
        <div className="p-4 bg-info-bg border border-info-border rounded-lg mb-5">
          <p className="text-xs font-semibold text-info-DEFAULT mb-2">
            Best results: upload these together
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs text-text-secondary">
            {[
              "Commercial Invoice",
              "Packing List",
              "Air Waybill / Bill of Lading",
              "Certificate of Origin",
            ].map(doc => (
              <div key={doc} className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-info-DEFAULT flex-shrink-0" />
                {doc}
              </div>
            ))}
          </div>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="card mb-5 overflow-hidden">
            <div className="card-header">
              <h3 className="text-xs font-semibold text-text-primary">
                Files ({files.length})
              </h3>
            </div>
            <div className="divide-y divide-border">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3">
                  <File className="w-4 h-4 text-text-tertiary flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text-primary truncate">{f.file.name}</p>
                    <p className="text-2xs text-text-tertiary">
                      {(f.file.size / 1024 / 1024).toFixed(2)} MB
                      {f.docType && ` · ${f.docType.replace(/_/g, " ")}`}
                    </p>
                  </div>

                  {f.status === "uploading" && (
                    <Loader2 className="w-4 h-4 text-accent animate-spin flex-shrink-0" />
                  )}
                  {f.status === "done" && (
                    <CheckCircle className="w-4 h-4 text-success-DEFAULT flex-shrink-0" />
                  )}
                  {f.status === "error" && (
                    <div className="flex items-center gap-1">
                      <AlertCircle className="w-4 h-4 text-error-DEFAULT" />
                      <span className="text-2xs text-error-DEFAULT">{f.error}</span>
                    </div>
                  )}
                  {f.status === "pending" && (
                    <button
                      onClick={() => removeFile(i)}
                      className="text-text-tertiary hover:text-error-DEFAULT transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        {files.length > 0 && (
          <div className="flex items-center gap-3">
            <button
              className="btn btn-primary"
              onClick={uploadAll}
              disabled={processing || files.every(f => f.status !== "pending")}
            >
              {processing ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Processing…</>
              ) : (
                <><Upload className="w-4 h-4" /> Upload & Extract ({files.filter(f => f.status === "pending").length} files)</>
              )}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setFiles([])}
              disabled={processing}
            >
              Clear All
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
