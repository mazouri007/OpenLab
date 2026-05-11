import { createBrowserRouter } from "react-router-dom";

import App from "../App";
import DashboardPage from "../pages/DashboardPage";
import ReviewPage from "../pages/ReviewPage";
import TestGenPage from "../pages/TestGenPage";
import ChatPage from "../pages/ChatPage";
import GithubPage from "../pages/GithubPage";
import KnowledgePage from "../pages/KnowledgePage";
import ModelSettingsPage from "../pages/ModelSettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "review", element: <ReviewPage /> },
      { path: "testgen", element: <TestGenPage /> },
      { path: "chat", element: <ChatPage /> },
      { path: "github", element: <GithubPage /> },
      { path: "kb", element: <KnowledgePage /> },
      { path: "models", element: <ModelSettingsPage /> },
    ],
  },
]);

