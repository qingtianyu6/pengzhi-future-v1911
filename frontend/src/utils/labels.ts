export const actionLabels: Record<string, string> = {
 list_greenhouses: '查询大棚', get_current_environment: '读取本棚环境', get_environment_history: '查看环境历史',
 get_future_prediction: '查看环境预测', get_active_warnings: '读取活动预警', get_farm_tasks: '查看农事任务',
 get_risk_summary: '汇总风险', get_similar_cases: '查找历史案例', search_agriculture_knowledge: '检索农业知识',
 get_disease_record: '查看叶片识别记录', create_task_draft: '整理任务草稿', create_farm_task: '创建人工任务',
 update_farm_task: '更新任务安排', schedule_recheck: '安排复查', close_farm_task: '记录任务完成',
 save_case_memory: '保存复盘记录', generate_greenhouse_report: '生成大棚报告',
 low: '低', medium: '中', high: '高', urgent: '紧急', temperature: '温度', air_humidity: '空气湿度',
 soil_moisture: '土壤湿度', co2_concentration: '二氧化碳', completed: '已完成', pending: '待执行', scheduled: '已安排', running: '处理中',
 ventilation: '通风检查', ventilation_check: '通风检查', manual_observation: '人工观察',
 humidity_control: '湿度管理', sensor_inspection: '传感器检查', field_inspection: '现场复核',
 irrigation_check: '灌溉检查', shading_check: '遮阴检查', expert_review: '专家复核', sample_collection: '采集样本',
 condensation_inspection: '结露检查', isolation_check: '隔离检查', heating_check: '保温检查',
 attention: '需关注', warning: '预警', critical: '高风险', normal: '正常',
 environment_record: '环境记录', environment_prediction: '环境预测', risk_assessment: '风险评估',
 decision_recommendation: '决策建议', decision_plan: '处置方案', disease_risk_event: '病害风险事件',
 warning_event: '预警事件', farm_task: '农事任务', task: '农事任务', execution_feedback: '执行反馈',
 disease_review: '病害人工复核', candidate_action: '候选方案', intervention: '处置记录' }
export const label = (value: string | null | undefined) => value ? actionLabels[value] ?? value : '暂无'
