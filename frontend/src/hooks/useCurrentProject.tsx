import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";

import { listProjects } from "../api/platform";
import type { Project } from "../types/domain";

type ProjectContextValue = {
  projects: Project[];
  currentProject: Project | null;
  projectId: string;
  setProjectId: (projectId: string) => void;
  isLoading: boolean;
};

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: PropsWithChildren) {
  const { data = [], isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    if (!projectId && data[0]?.id) {
      setProjectId(data[0].id);
    }
  }, [data, projectId]);

  const value = useMemo<ProjectContextValue>(
    () => ({
      projects: data,
      currentProject: data.find((project) => project.id === projectId) ?? data[0] ?? null,
      projectId: projectId || data[0]?.id || "",
      setProjectId,
      isLoading,
    }),
    [data, isLoading, projectId],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useCurrentProject() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useCurrentProject must be used within ProjectProvider");
  }
  return context;
}
