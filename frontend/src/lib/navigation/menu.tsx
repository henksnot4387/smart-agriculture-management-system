import type { MenuDataItem } from "@ant-design/pro-components";
import {
  ApartmentOutlined,
  AreaChartOutlined,
  CalendarOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined,
  UnorderedListOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";

export const systemMenuItems: MenuDataItem[] = [
  {
    path: "/dashboard",
    name: "数据总览",
    icon: <DashboardOutlined />,
  },
  {
    path: "/monitor",
    name: "温室监测",
    icon: <ApartmentOutlined />,
  },
  {
    key: "sensor-data-group",
    name: "传感器数据",
    icon: <ExperimentOutlined />,
    children: [
      {
        path: "/sensor/history",
        name: "历史趋势",
      },
    ],
  },
  {
    path: "/vision",
    name: "病害识别",
    icon: <WarningOutlined />,
  },
  {
    key: "ai-insights-group",
    name: "智能建议",
    icon: <RobotOutlined />,
    children: [
      {
        path: "/ai-insights",
        name: "模块总览",
      },
      {
        path: "/ai-insights/recommendations",
        name: "AI建议草稿与入库",
      },
      {
        path: "/ai-insights/summary",
        name: "AI智能解析",
      },
      {
        path: "/ai-insights/knowledge",
        name: "本地知识库",
      },
    ],
  },
  {
    path: "/tasks",
    name: "任务中心",
    icon: <UnorderedListOutlined />,
  },
  {
    path: "/expert",
    name: "专家审批",
    icon: <SafetyCertificateOutlined />,
  },
  {
    path: "/worker",
    name: "工人执行",
    icon: <TeamOutlined />,
  },
  {
    path: "/users",
    name: "用户与权限",
    icon: <UserOutlined />,
  },
  {
    key: "settings-group",
    name: "系统设置",
    icon: <SettingOutlined />,
    children: [
      {
        path: "/settings",
        name: "设置总览",
      },
      {
        path: "/settings/horticulture",
        name: "园艺设置",
      },
      {
        path: "/settings/plant-protection",
        name: "植保设置",
      },
      {
        path: "/settings/climate",
        name: "环控设置",
      },
      {
        path: "/settings/fertigation",
        name: "水肥设置",
      },
    ],
  },
  {
    path: "/scheduler",
    name: "调度中心",
    icon: <CalendarOutlined />,
  },
  {
    path: "/observability",
    name: "可观测中心",
    icon: <AreaChartOutlined />,
  },
];

const flatMenuEntries = [
  { path: "/dashboard", title: "数据总览", description: "查看全场传感器总览、分区态势和关键业务状态。" },
  { path: "/monitor", title: "温室监测", description: "查看温室/分区运行状态、气候趋势和告警信息。" },
  { path: "/sensor/history", title: "传感器数据", description: "查看温湿度、EC、pH 的历史趋势与时序查询结果。" },
  { path: "/vision", title: "病害识别", description: "上传图片、跟踪识别结果和异步任务状态。" },
  { path: "/ai-insights", title: "智能建议", description: "智能建议模块总览页，选择建议草稿、AI智能解析或知识检索。" },
  { path: "/ai-insights/recommendations", title: "AI建议草稿与入库", description: "先生成建议草稿，再人工确认写入任务中心。" },
  { path: "/ai-insights/summary", title: "AI智能解析", description: "查看近24小时双层解析、风险排行和证据依据。" },
  { path: "/ai-insights/knowledge", title: "本地知识库", description: "按分类和关键词检索知识条目与来源依据。" },
  { path: "/tasks", title: "任务中心", description: "查看系统内任务的创建、流转与执行情况。" },
  { path: "/expert", title: "专家审批", description: "集中处理待审批的 AI 建议与任务。" },
  { path: "/worker", title: "工人执行", description: "查看工单、执行状态和回传结果。" },
  { path: "/users", title: "用户与权限", description: "管理用户、角色和权限分配。" },
  { path: "/settings", title: "系统设置", description: "查看接入配置、运行状态和系统参数。" },
  { path: "/settings/horticulture", title: "园艺设置", description: "配置打叶、落蔓、绕头等园艺任务自动触发策略。" },
  { path: "/settings/plant-protection", title: "植保设置", description: "配置打药、消毒、病害复检等植保策略与任务触发。" },
  { path: "/settings/climate", title: "环控设置", description: "配置环控策略复核、执行器校准和巡检触发周期。" },
  { path: "/settings/fertigation", title: "水肥设置", description: "配置 EC/pH、施肥机与灌溉执行的自动任务触发规则。" },
  { path: "/scheduler", title: "调度中心", description: "统一管理系统定时任务、执行历史和任务状态。" },
  { path: "/observability", title: "可观测中心", description: "查看错误请求、慢接口排行与任务失败链路。" },
] as const;

export function getPageMeta(pathname: string) {
  const exact = flatMenuEntries.find((entry) => pathname === entry.path);
  if (exact) {
    return exact;
  }

  const matchedPrefix = [...flatMenuEntries]
    .filter((entry) => pathname.startsWith(`${entry.path}/`))
    .sort((left, right) => right.path.length - left.path.length)[0];

  return (
    matchedPrefix ?? {
      title: "智慧农业管理系统",
      description: "农业业务与设备数据的统一运营中枢。",
    }
  );
}
