export type CropBatchStatus = 'growing' | 'harvested' | 'closed'
export type CropType = 'tomato' | 'muskmelon' | 'other' | 'unknown'
export type GrowthStage = '苗期' | '营养生长期' | '伸蔓期' | '开花坐果期' | '果实膨大期' | '成熟采收期' | '规则不可用'

export interface CropBatch {
  id: number
  greenhouse_id: number
  batch_code: string
  variety: string
  crop_type: CropType
  planted_at: string
  expected_harvest_at: string | null
  growth_stage: GrowthStage
  growth_day: number
  stage_updated_at: string
  is_stage_manually_set: boolean
  status: CropBatchStatus
  created_at: string
  updated_at: string
}

export interface CropBatchInput {
  batch_code: string
  variety: string
  crop_type: CropType
  planted_at: string
  expected_harvest_at?: string
  growth_stage?: GrowthStage
  status: CropBatchStatus
}
