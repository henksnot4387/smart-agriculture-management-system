import type { DashboardRange } from "@/src/types/sensor";
import { Segmented } from "antd";

type RangeToggleProps = {
  value: DashboardRange;
  disabled?: boolean;
  onChange: (nextRange: DashboardRange) => void;
};

export function RangeToggle({ value, disabled = false, onChange }: RangeToggleProps) {
  return (
    <Segmented
      name="dashboard-range-toggle"
      value={value}
      onChange={(nextValue) => onChange(nextValue as DashboardRange)}
      disabled={disabled}
      options={[
        { label: "近24小时", value: "24h" },
        { label: "近7天", value: "7d" },
      ]}
    />
  );
}
