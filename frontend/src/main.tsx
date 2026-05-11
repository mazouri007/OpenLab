import React from "react";
import ReactDOM from "react-dom/client";
import { App as AntApp } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { router } from "./routes/router";
import "antd/dist/reset.css";
import "./styles.css";
import { ProjectProvider } from "./hooks/useCurrentProject";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AntApp>
      <QueryClientProvider client={queryClient}>
        <ProjectProvider>
          <RouterProvider router={router} />
        </ProjectProvider>
      </QueryClientProvider>
    </AntApp>
  </React.StrictMode>,
);
