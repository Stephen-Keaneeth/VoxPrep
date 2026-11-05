"use client";

import React from "react";
import { useAppStore } from "@/store/useStore";
import HomeDashboard from "@/components/sections/HomeDashboard";
import InterviewAgent from "@/components/sections/InterviewAgent";
import CommunicationAgent from "@/components/sections/CommunicationAgent";
import InterviewDashboard from "@/components/sections/InterviewDashboard";
import CommunicationDashboard from "@/components/sections/CommunicationDashboard";

export default function Page() {
  const { activeSection } = useAppStore();

  return (
    <>
      {activeSection === 1 && <HomeDashboard />}
      {activeSection === 2 && <InterviewAgent />}
      {activeSection === 3 && <CommunicationAgent />}
      {activeSection === 4 && <InterviewDashboard />}
      {activeSection === 5 && <CommunicationDashboard />}
    </>
  );
}

