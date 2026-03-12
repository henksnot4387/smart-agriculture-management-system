import { Empty } from "antd";
import { ProCard } from "@ant-design/pro-components";

export function DashboardEmptyState() {
  return (
    <ProCard>
      <Empty
        description="当前时间范围内暂无传感器数据，请先执行数据同步或等待下一轮采集。"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    </ProCard>
  );
}
