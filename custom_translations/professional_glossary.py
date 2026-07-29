"""
Professional ERP glossary for Chinese translations.

This module provides manually-curated, professionally-accurate Chinese
translations for key ERP terms. These override any auto-translated or
locale-pack translations that don't match professional accounting/ERP
standards in mainland China.

Usage:
    from custom_translations.professional_glossary import apply_professional_glossary
    apply_professional_glossary()  # Writes to zh.csv with overwrite=True

Or via bench command:
    bench --site {site} custom-translations-apply-glossary
"""

# Professional ERP glossary - curated by domain experts
# These follow Chinese accounting standards (企业会计准则) and mainstream
# ERP terminology used in mainland China (用友/金蝶/SAP中文版 conventions).
#
# Format: "English source": "Chinese translation"
PROFESSIONAL_GLOSSARY = {
    # ========== Accounting 会计 (following 企业会计准则) ==========
    "Journal Entry": "日记账分录",
    "Journal Entry Account": "日记账分录科目",
    "Journal Entry Template": "日记账分录模板",
    "Journal Entry Type": "日记账分录类型",
    "Stock Ledger Entry": "库存分类账分录",
    "General Ledger": "总分类账",
    "Trial Balance": "试算平衡表",
    "Balance Sheet": "资产负债表",
    "Profit and Loss": "利润表",
    "Chart of Accounts": "会计科目表",
    "Cost Center": "成本中心",
    "Payment Entry": "付款凭证",
    "Account Receivable": "应收账款",
    "Account Payable": "应付账款",
    "Account Receivable (AR)": "应收账款",
    "Account Payable (AP)": "应付账款",
    "Bank Reconciliation": "银行对账",
    "Bank Reconciliation Statement": "银行对账单",
    "Account Group": "科目组",
    "Account Type": "科目类型",
    "Finance Book": "账簿",
    "Fiscal Year": "会计年度",
    "Accounting Period": "会计期间",
    "Closing Entry": "结账分录",
    "Opening Entry": "开账分录",
    "Deferred Revenue": "递延收入",
    "Deferred Expense": "递延费用",
    "Depreciation Method": "折旧方法",
    "Asset Depreciation Schedule": "资产折旧计划",
    "Asset": "资产",
    "Asset Category": "资产类别",
    "Account": "科目",
    "Period": "期间",
    "GL Entry": "总账分录",
    "Payment Reconciliation": "付款对账",
    "Invoice Discounting": "发票贴现",
    "Accounts Settings": "会计设置",
    "Accounting Dimension": "会计维度",
    "Accounting Statement": "会计报表",
    "Cost of Goods Sold": "主营业务成本",
    "Cost Center Allocation": "成本中心分摊",
    "Budget": "预算",

    # ========== Inventory 库存 ==========
    "Stock Entry": "库存移动单",
    "Stock Entry Type": "库存移动类型",
    "Stock Entry Detail": "库存移动明细",
    "Stock Reconciliation": "库存盘点调账",
    "Stock Reservation Entry": "库存预留分录",
    "Serial No": "序列号",
    "Serial No Status": "序列号状态",
    "Batch": "批次",
    "Batch Split": "批次拆分",
    "Warehouse": "仓库",
    "Item Code": "物料编码",
    "Item Group": "物料组",
    "Item Price": "物料价格",
    "Item Alternative": "替代物料",
    "Item Variant": "派生物料",
    "Item Manufacturer": "物料制造商",
    "Bin": "库位",
    "Stock UOM": "库存单位",
    "Valuation Rate": "计价成本",
    "Landed Cost Voucher": "到岸成本凭证",
    "Quality Inspection": "质量检验单",
    "Stock Settings": "库存设置",
    "Stock Balance": "库存余额",
    "Stock Report": "库存报表",
    "Actual Qty": "实际数量",
    "Available Qty": "可用数量",
    "Ordered Qty": "订购数量",
    "Reserved Qty": "预留数量",
    "Projected Qty": "预计数量",

    # ========== Sales/Purchase 销售采购 ==========
    "Quotation": "报价单",
    "Sales Order": "销售订单",
    "Purchase Order": "采购订单",
    "Delivery Note": "送货单",
    "Delivery Note Item": "送货单明细",
    "Purchase Receipt": "采购收货单",
    "Purchase Receipt Item": "采购收货单明细",
    "Sales Invoice": "销售发票",
    "Purchase Invoice": "采购发票",
    "Supplier Quotation": "供应商报价单",
    "Material Request": "物料申请单",
    "Sales Order Item": "销售订单明细",
    "Purchase Order Item": "采购订单明细",
    "POS Profile": "POS配置",
    "Price List": "价格表",
    "Pricing Rule": "定价规则",
    "Promotional Scheme": "促销方案",
    "Coupon Code": "优惠券",
    "Shipping Rule": "运费规则",
    "Tax Rule": "税务规则",
    "Tax Category": "税目分类",
    "Sales Person": "销售员",
    "Sales Settings": "销售设置",
    "Buying Settings": "采购设置",
    "Customer Issue": "客户问题",

    # ========== HR 人力资源 ==========
    "Leave Application": "请假申请",
    "Leave Type": "假期类型",
    "Holiday List": "假期清单",
    "Payroll Entry": "工资单分录",
    "Salary Slip": "工资条",
    "Attendance": "考勤",
    "Employee Onboarding": "员工入职",
    "Exit Interview": "离职面谈",
    "Salary Structure": "薪资结构",
    "Employee Tax Exemption": "员工免税额",
    "Employee Advance": "员工预支款",
    "Expense Claim": "费用报销",
    "Expense Claim Type": "费用报销类型",
    "Activity Cost": "活动成本",
    "Timesheet": "工时表",
    "Project Status": "项目状态",
    "HR Settings": "人事设置",
    "Payroll Settings": "工资单设置",
    "Employee Settings": "员工设置",
    "Leave Settings": "休假设置",
    "Shift Assignment": "排班分配",
    "Shift Type": "班次类型",
    "Shift Request": "换班申请",
    "Job Applicant": "职位申请人",
    "Job Offer": "录用通知",
    "Job Opening": "职位空缺",
    "Designation": "职位",
    "Department": "部门",
    "Branch": "分支机构",
    "Employment Type": "雇佣类型",
    "Grade": "职级",

    # ========== Manufacturing 制造 ==========
    "Work Order": "工单",
    "Bill of Materials": "物料清单",
    "BOM": "物料清单",
    "BOM Explosion": "BOM展开",
    "BOM Explosion Item": "BOM展开物料",
    "Operation": "工序",
    "Workstation": "工作站",
    "Routing": "工艺路线",
    "Production Plan": "生产计划",
    "Job Card": "作业卡",
    "Work Order Operation": "工单工序",
    "Manufacturing Settings": "制造设置",
    "Production Plan Item": "计划生产物料",
    "Work Order Item": "工单物料",
    "BOM Item": "BOM物料",
    "BOM Operation": "BOM工序",
    "BOM Scrap Item": "BOM废料",
    "BOM Update Tool": "BOM更新工具",
    "Operation Completion": "工序完成",
    "Capacity Planning": "计划产能",
    "Downtime Entry": "停机记录",

    # ========== CRM ==========
    "Lead": "线索",
    "Opportunity": "商机",
    "Prospect": "潜在客户",
    "Customer Group": "客户组",
    "Territory": "销售区域",
    "Campaign": "营销活动",
    "Lead Source": "线索来源",
    "Opportunity Type": "商机类型",
    "CRM Settings": "CRM设置",
    "Lead Owner": "线索负责人",
    "Opportunity Owner": "商机负责人",
    "Sales Stage": "销售阶段",
    "Sales Cycle": "销售周期",
    "Customer": "客户",
    "Supplier": "供应商",
    "Contact": "联系人",
    "Address": "地址",
    "Address Title": "地址标题",

    # ========== System/System Settings 系统设置 ==========
    "Custom Field": "自定义字段",
    "Custom Script": "自定义脚本",
    "Property Setter": "属性设置器",
    "DocType": "文档类型",
    "DocField": "文档字段",
    "DocPerm": "文档权限",
    "Workflow": "工作流",
    "Workflow State": "工作流状态",
    "Workflow Action": "工作流动作",
    "Email Template": "邮件模板",
    "Print Format": "打印格式",
    "Role": "角色",
    "Module Def": "模块定义",
    "Module": "模块",
    "User": "用户",
    "System Settings": "系统设置",
    "System User": "系统用户",
    "Website User": "网站用户",

    # ========== Maintenance 维护 ==========
    "Maintenance Schedule": "维护调度",
    "Maintenance Visit": "维护访问",
    "Maintenance Order": "维护工单",
    "Maintenance Team": "维护团队",
    "Maintenance Request": "维护请求",

    # ========== Common messages 常用消息 ==========
    "No Items Found": "未找到物料",
    "Please select a Customer": "请选择客户",
    "Are you sure you want to proceed?": "确定要继续吗？",
    "This action cannot be undone": "此操作无法撤销",
    "Insufficient stock for item {0}": "物料 {0} 库存不足",
    "Cannot cancel because {0} is linked with {1}": "无法取消，因为 {0} 与 {1} 存在关联",
    "Journal Entry posted successfully": "日记账分录已过账",
    "Journal Entry cancelled successfully": "日记账分录已取消",
    "Purchase Receipt submitted": "采购收货单已提交",
    "Sales Invoice cancelled": "销售发票已取消",
    "Work Order created successfully": "工单已创建",
    "BOM explosion for item {0} failed": "物料 {0} 的BOM展开失败",
    "Lead converted to Customer successfully": "线索已成功转换为客户",
    "Stock Ledger Entry created": "库存分类账分录已创建",
    "Stock Entry created successfully": "库存移动单已创建",
    "Sales Order created successfully": "销售订单已创建",
    "Purchase Order created successfully": "采购订单已创建",
    "Delivery Note submitted": "送货单已提交",
    "Quotation created successfully": "报价单已创建",
    "Opportunity created successfully": "商机已创建",
    "Leave Application submitted": "请假申请已提交",
    "Leave Application approved": "请假申请已批准",
    "Salary Slip created successfully": "工资条已创建",
    "Payroll Entry submitted": "工资单分录已提交",
}


def apply_professional_glossary():
    """
    Apply professional ERP glossary to translations CSV.

    Writes all professional translations to zh.csv with overwrite=True,
    so they override any auto-translated or locale-pack translations.

    This is safe because these are manually-curated, expert-reviewed
    translations that follow Chinese accounting standards.

    Returns: number of translations applied
    """
    from custom_translations.utils import _append_to_csv, APP_NAME
    import frappe

    count = len(PROFESSIONAL_GLOSSARY)
    _append_to_csv(PROFESSIONAL_GLOSSARY, overwrite=True)

    frappe.logger(APP_NAME).info(
        f"Applied {count} professional glossary entries to CSV"
    )
    return count
