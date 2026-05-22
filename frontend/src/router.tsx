import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { TriageScreen } from "@/screens/TriageScreen";
import { CrisisExplorerScreen } from "@/screens/CrisisExplorerScreen";
import { CompareScreen } from "@/screens/CompareScreen";
import { AskScreen } from "@/screens/AskScreen";
import { MethodologyScreen } from "@/screens/MethodologyScreen";
import { CbpfScreen } from "@/screens/CbpfScreen";
import { NotFoundScreen } from "@/screens/NotFoundScreen";

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <TriageScreen /> },
      { path: "/crisis/:iso3", element: <CrisisExplorerScreen /> },
      { path: "/compare", element: <CompareScreen /> },
      { path: "/ask", element: <AskScreen /> },
      { path: "/methodology", element: <MethodologyScreen /> },
      { path: "/cbpf", element: <CbpfScreen /> },
      { path: "*", element: <NotFoundScreen /> },
    ],
  },
]);
