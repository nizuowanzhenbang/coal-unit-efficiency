import { useEffect, useState } from "react";
import { api } from "./client";
import { Unit } from "./types";

export function useUnits() {
  const [units, setUnits] = useState<Unit[]>([]);
  useEffect(() => {
    api.get<Unit[]>("/units").then((r) => setUnits(r.data));
  }, []);
  return units;
}
