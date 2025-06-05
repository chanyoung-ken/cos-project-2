#include "process_manager.h"
#include "opcode.h"
#include "byte_op.h"
#include "setting.h"
#include <cstring>
#include <iostream>
#include <ctime>
#include <algorithm>
#include <vector>
#include <cmath>
using namespace std;

ProcessManager::ProcessManager()
{
  this->num = 0;
}

void ProcessManager::init()
{
}

uint8_t *ProcessManager::processData(DataSet *ds, int *dlen)
{
  uint8_t *ret, *p;
  int num;
  HouseData *house;
  TemperatureData *tdata;
  HumidityData *hdata;
  PowerData *pdata;
  ret = (uint8_t *)malloc(BUFLEN);
  time_t ts;
  struct tm *tm;

  // 데이터 수집 / Data collection
  tdata = ds->getTemperatureData();
  hdata = ds->getHumidityData();
  num = ds->getNumHouseData();
  
  // 전력 데이터 벡터 생성 / Create power data vector for aggregation
  vector<float> power_values;
  for (int i = 0; i < num; i++) {
    house = ds->getHouseData(i);
    pdata = house->getPowerData();
    power_values.push_back((float)pdata->getValue());
  }
  
  // 온도 집계 데이터 (민감정보 제거됨) / Temperature aggregation (sensitive info removed)
  float temp_avg = (float)((tdata->getMin() + tdata->getMax()) / 2.0);
  float temp_min = (float)tdata->getMin();
  float temp_max = (float)tdata->getMax();
  
  // 습도 집계 데이터 / Humidity aggregation
  float humid_avg = (float)((hdata->getMin() + hdata->getMax()) / 2.0);
  float humid_min = (float)hdata->getMin();
  float humid_max = (float)hdata->getMax();
  
  // 전력 집계 계산 / Power aggregation calculation
  float power_avg = 0.0f, power_min = 0.0f, power_max = 0.0f;
  float power_p25 = 0.0f, power_p75 = 0.0f; // 25th, 75th percentiles
  
  if (!power_values.empty()) {
    // 평균 계산 / Calculate average
    float sum = 0.0f;
    for (float val : power_values) {
      sum += val;
    }
    power_avg = sum / power_values.size();
    
    // 최대/최소 계산 / Calculate min/max
    power_min = *min_element(power_values.begin(), power_values.end());
    power_max = *max_element(power_values.begin(), power_values.end());
    
    // 퍼센타일 계산을 위한 정렬 / Sort for percentile calculation
    sort(power_values.begin(), power_values.end());
    int size = power_values.size();
    
    // 25th percentile (Q1)
    int idx_25 = (int)ceil(0.25 * size) - 1;
    if (idx_25 < 0) idx_25 = 0;
    power_p25 = power_values[idx_25];
    
    // 75th percentile (Q3)
    int idx_75 = (int)ceil(0.75 * size) - 1;
    if (idx_75 >= size) idx_75 = size - 1;
    power_p75 = power_values[idx_75];
  }
  
  // 타임스탬프에서 월 정보 추출 (개인정보 아님) / Extract month info from timestamp (not personal info)
  ts = ds->getTimestamp();
  tm = localtime(&ts);
  int month = tm->tm_mon + 1;
  
  // 버퍼 초기화 및 데이터 패킹 (big-endian) / Initialize buffer and pack data (big-endian)
  memset(ret, 0, BUFLEN);
  *dlen = 0;
  p = ret;
  
  // 온도 집계 데이터 저장 (4바이트씩 float) / Store temperature aggregation data (4 bytes float each)
  uint32_t temp_avg_bits = *(uint32_t*)&temp_avg;
  uint32_t temp_min_bits = *(uint32_t*)&temp_min;
  uint32_t temp_max_bits = *(uint32_t*)&temp_max;
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(temp_avg_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(temp_min_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(temp_max_bits, p);
  *dlen += 12;
  
  // 습도 집계 데이터 저장 / Store humidity aggregation data
  uint32_t humid_avg_bits = *(uint32_t*)&humid_avg;
  uint32_t humid_min_bits = *(uint32_t*)&humid_min;
  uint32_t humid_max_bits = *(uint32_t*)&humid_max;
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(humid_avg_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(humid_min_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(humid_max_bits, p);
  *dlen += 12;
  
  // 전력 집계 데이터 저장 (평균, 최소, 최대, 퍼센타일) / Store power aggregation data (avg, min, max, percentiles)
  uint32_t power_avg_bits = *(uint32_t*)&power_avg;
  uint32_t power_min_bits = *(uint32_t*)&power_min;
  uint32_t power_max_bits = *(uint32_t*)&power_max;
  uint32_t power_p25_bits = *(uint32_t*)&power_p25;
  uint32_t power_p75_bits = *(uint32_t*)&power_p75;
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(power_avg_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(power_min_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(power_max_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(power_p25_bits, p);
  VAR_TO_MEM_4BYTES_BIG_ENDIAN(power_p75_bits, p);
  *dlen += 20;
  
  // 월 정보 저장 (1바이트) / Store month info (1 byte)
  VAR_TO_MEM_1BYTE_BIG_ENDIAN(month, p);
  *dlen += 1;
  
  // 총 데이터 길이: 45바이트 (온도 12 + 습도 12 + 전력 20 + 월 1)
  // Total data length: 45 bytes (temp 12 + humid 12 + power 20 + month 1)

  return ret;
}
