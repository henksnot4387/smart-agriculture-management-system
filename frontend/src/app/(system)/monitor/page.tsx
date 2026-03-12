import { ModulePlaceholder } from "@/src/components/system/module-placeholder";

export default function MonitorPage() {
  return <ModulePlaceholder title="温室监测" subtitle="查看温室、分区和异常状态。" relatedTasks={["传感器查询接口", "时序策略", "可观测性"]} />;
}
