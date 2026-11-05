"use client";

import React, { useState, useRef } from "react";
import { useAppStore, ResumeData } from "@/store/useStore";
import { toast } from "@/store/useToast";
import { extractTextFromFile, analyzeResumeText } from "@/lib/resumeParser";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  X,
  Sparkles,
  Briefcase,
  Layers,
  Trash2,
} from "lucide-react";

export default function ResumeUploadModal() {
  const {
    isSetupModalOpen,
    setSetupModalOpen,
    resume,
    setResume,
    isResumeBased,
    setIsResumeBased,
    resetQuestions,
  } = useAppStore();

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  if (!isSetupModalOpen) return null;

  const handleFileUpload = async (file: File) => {
    setIsProcessing(true);
    try {
      const text = await extractTextFromFile(file);
      const analysis = analyzeResumeText(text, file.name);

      const newResume: ResumeData = {
        fileName: file.name,
        fileSize: `${(file.size / 1024).toFixed(1)} KB`,
        uploadedAt: "Just now",
        candidateName: analysis.candidateName || "Candidate",
        targetRole: analysis.targetRole,
        experienceLevel: analysis.experienceLevel,
        skills: analysis.skills,
        recentCompany: analysis.recentCompany,
        summary: analysis.summary,
        customQuestions: analysis.customQuestions,
      };

      setResume(newResume);
      setIsResumeBased(true);
      resetQuestions();
      toast.success(
        "Resume analyzed successfully",
        `Tailored interview questions active for ${newResume.targetRole}.`
      );
    } catch (err) {
      console.warn("Resume parsing error:", err);
      toast.warning("Standard analysis fallback", "Applied default engineering questions.");
    } finally {
      setIsProcessing(false);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => {
    setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in">
      <div className="card-clean bg-[#0d1424] border border-blue-500/20 max-w-xl w-full p-6 space-y-5 rounded-xl shadow-2xl relative">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-3 border-b border-subtle">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Interview Customization & Resume</h3>
              <p className="text-xs text-slate-400">
                Upload your resume to generate tailored, project-specific interview questions.
              </p>
            </div>
          </div>
          <button
            onClick={() => setSetupModalOpen(false)}
            className="text-slate-400 hover:text-white p-1 rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tailored Mode Toggle */}
        <div className="flex items-center justify-between p-3.5 rounded-lg bg-[#0a101d] border border-subtle">
          <div className="space-y-0.5">
            <span className="text-xs font-semibold text-white flex items-center gap-1.5">
              <span>Resume-Adaptive Interviewing</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-400">
                Recommended
              </span>
            </span>
            <p className="text-[11px] text-slate-400">
              The AI interviewer will grill your actual past projects, tech stack, and experience.
            </p>
          </div>
          <button
            onClick={() => setIsResumeBased(!isResumeBased)}
            className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 ${
              isResumeBased ? "bg-blue-600" : "bg-slate-700"
            }`}
          >
            <div
              className={`w-5 h-5 rounded-full bg-white transition-transform ${
                isResumeBased ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>

        {/* Upload Drop Zone */}
        {!resume || isProcessing ? (
          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
              isDragging
                ? "border-blue-400 bg-blue-500/10"
                : "border-slate-700 hover:border-slate-500 bg-[#0a101d]/50"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
            />
            <div className="flex flex-col items-center justify-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div className="text-xs text-white font-medium">
                {isProcessing ? "Parsing resume with LLM..." : "Click to upload or drag & drop"}
              </div>
              <div className="text-[11px] text-slate-400">Supports PDF, DOCX, or TXT (Max 10MB)</div>
            </div>
          </div>
        ) : (
          /* Active Parsed Resume Card */
          <div className="p-4 rounded-xl bg-[#0a101d] border border-blue-500/30 space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-subtle">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                    <span>{resume.fileName}</span>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 inline" />
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    {resume.fileSize} · Uploaded {resume.uploadedAt}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded transition-colors"
                >
                  Replace
                </button>
                <button
                  onClick={() => {
                    setResume(null);
                    toast.info("Resume disconnected", "Switched back to standard system design questions.");
                  }}
                  className="text-red-400 hover:text-red-300 p-1 rounded transition-colors"
                  title="Remove Resume"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
            />

            {/* Extracted Insights Preview */}
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2 text-slate-300">
                <Briefcase className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span>
                  Detected Target Role: <strong className="text-white">{resume.targetRole}</strong>
                </span>
              </div>

              <div className="flex items-start gap-2 text-slate-300">
                <Layers className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <span className="text-slate-400 mr-1.5">Target Skills to Assess:</span>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {resume.skills.map((skill) => (
                      <span
                        key={skill}
                        className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center justify-between pt-2 border-t border-subtle">
          <button
            onClick={() => {
              setIsResumeBased(false);
              setSetupModalOpen(false);
            }}
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            Use Standard Generic Questions
          </button>

          <button
            onClick={() => setSetupModalOpen(false)}
            className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors"
          >
            Save & Apply to Call
          </button>
        </div>
      </div>
    </div>
  );
}

