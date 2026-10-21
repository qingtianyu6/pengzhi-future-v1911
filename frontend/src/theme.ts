import type { ThemeConfig } from 'antd'

/** Shared across the public site, authentication and operational workspaces. */
export const platformTheme: ThemeConfig = {
  token: {
    colorPrimary: '#21644d', colorInfo: '#21644d', colorSuccess: '#34815e',
    colorWarning: '#b47b26', colorError: '#c45344', colorText: '#233f35',
    colorTextSecondary: '#66786f', colorBgLayout: '#f5f4ed', colorBgContainer: '#fffefa',
    colorBorder: '#d9e2d7', colorBorderSecondary: '#e6eae1',
    borderRadius: 10, borderRadiusLG: 18, controlHeight: 38,
    boxShadowSecondary: '0 12px 36px rgba(31, 60, 46, .08)',
    fontFamily: "'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif",
    fontSize: 15, fontSizeSM: 13, fontSizeLG: 16,
    fontSizeHeading1: 34, fontSizeHeading2: 22, fontSizeHeading3: 18,
    fontSizeHeading4: 16, fontSizeHeading5: 15, lineHeight: 1.75,
  },
  components: {
    Button: { primaryShadow: '0 3px 8px rgba(33, 100, 77, .12)', fontWeight: 500 },
    Card: { headerFontSize: 18, headerHeight: 56, bodyPadding: 24 },
    Table: { cellPaddingBlock: 14, headerBg: '#f1f5ec', headerColor: '#4f675b' },
    Tabs: { horizontalItemGutter: 26, titleFontSize: 14 },
    Menu: { itemBorderRadius: 10, itemHeight: 42 },
    Modal: { borderRadiusLG: 20 }, Drawer: { paddingLG: 24 },
  },
}
