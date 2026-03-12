import { Alert } from "antd";

type DashboardErrorBannerProps = {
  message: string;
};

export function DashboardErrorBanner({ message }: DashboardErrorBannerProps) {
  return <Alert type="warning" showIcon message="首页数据刷新告警" description={message} />;
}
