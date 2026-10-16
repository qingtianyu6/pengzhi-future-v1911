export function downloadEnvironmentTemplate() {
  const csv = 'recorded_at,temperature,air_humidity,soil_moisture,light_intensity,co2_concentration'
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'environment_data_template.csv'
  anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
