import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Alerts from "./pages/Alerts";
import Dashboard from "./pages/Dashboard";
import Deviation from "./pages/Deviation";
import Efficiency from "./pages/Efficiency";
import Login from "./pages/Login";
import Optimization from "./pages/Optimization";
import Reports from "./pages/Reports";
import Snapshots from "./pages/Snapshots";
import Units from "./pages/Units";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/units" element={<Units />} />
        <Route path="/snapshots" element={<Snapshots />} />
        <Route path="/efficiency" element={<Efficiency />} />
        <Route path="/deviation" element={<Deviation />} />
        <Route path="/optimization" element={<Optimization />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/alerts" element={<Alerts />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
