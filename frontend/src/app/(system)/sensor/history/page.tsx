import { ModulePlaceholder } from "@/src/components/system/module-placeholder";

export default function SensorHistoryPage() {
  return <ModulePlaceholder title="传感器数据" subtitle="查看历史趋势、时间区间和导出入口。" relatedTasks={["传感器查询接口", "时序策略", "联调回归"]} />;
}
