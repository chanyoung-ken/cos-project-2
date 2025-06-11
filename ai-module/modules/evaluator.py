import math
import numpy as np
import logging
from typing import List, Dict, Any, Tuple

class ModelEvaluator:
    """모델 예측 성능을 다양한 지표로 평가하는 클래스"""
    
    def __init__(self, threshold: float = 0.20):
        """
        Args:
            threshold: 정확도 판정을 위한 상대 오차 임계값 (기본값: 0.20)
        """
        self.threshold = threshold
        logging.info(f"모델 평가기 초기화 - 임계값: {threshold}")
    
    def calculate_metrics(self, actual_values: List[float], 
                         predicted_values: List[float], 
                         power_index: int) -> Dict[str, Any]:
        """
        예측값과 실제값을 비교하여 다양한 평가 지표를 계산
        
        Args:
            actual_values: 실제 데이터 시퀀스 (다차원 배열)
            predicted_values: 예측값 리스트
            power_index: 전력값이 위치한 인덱스
            
        Returns:
            평가 지표들을 담은 딕셔너리
        """
        if not actual_values or not predicted_values:
            return {"error": "데이터가 비어있습니다"}
        
        # 유효한 데이터만 추출 (-1이 아닌 예측값)
        valid_data = self._extract_valid_data(actual_values, predicted_values, power_index)
        
        if not valid_data['actual'] or not valid_data['predicted']:
            return {"error": "유효한 데이터가 없습니다"}
        
        actual = np.array(valid_data['actual'])
        predicted = np.array(valid_data['predicted'])
        
        # 다양한 평가 지표 계산
        metrics = {
            "num_samples": len(actual),
            "threshold": self.threshold,
            
            # 기본 정확도 (기존 방식)
            "accuracy": self._calculate_accuracy(actual, predicted),
            
            # 회귀 평가 지표들
            "mae": self._calculate_mae(actual, predicted),
            "mse": self._calculate_mse(actual, predicted),
            "rmse": self._calculate_rmse(actual, predicted),
            "mape": self._calculate_mape(actual, predicted),
            "r_squared": self._calculate_r_squared(actual, predicted),
            
            # 오차 분석
            "mean_error": self._calculate_mean_error(actual, predicted),
            "std_error": self._calculate_std_error(actual, predicted),
            
            # 상세 결과
            "correct_predictions": valid_data['correct'],
            "incorrect_predictions": valid_data['incorrect'],
            "actual_values": actual.tolist(),
            "predicted_values": predicted.tolist(),
            "errors": (predicted - actual).tolist(),
            "relative_errors": ((predicted - actual) / actual).tolist()
        }
        
        return metrics
    
    def _extract_valid_data(self, actual_values: List, predicted_values: List, 
                           power_index: int) -> Dict[str, List]:
        """유효한 데이터만 추출하고 정확/부정확 분류"""
        actual = []
        predicted = []
        correct = 0
        incorrect = 0
        
        for i, pred in enumerate(predicted_values):
            if pred == -1:  # 유효하지 않은 예측값 제외
                continue
                
            if i < len(actual_values):
                actual_val = actual_values[i][power_index]
                actual.append(actual_val)
                predicted.append(pred)
                
                # 정확도 판정 (상대 오차 기준)
                relative_error = abs((pred - actual_val) / actual_val)
                if relative_error <= self.threshold:
                    correct += 1
                else:
                    incorrect += 1
        
        return {
            'actual': actual,
            'predicted': predicted,
            'correct': correct,
            'incorrect': incorrect
        }
    
    def _calculate_accuracy(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """기존 방식의 정확도 계산 (상대 오차 기준)"""
        correct = 0
        for i in range(len(actual)):
            relative_error = abs((predicted[i] - actual[i]) / actual[i])
            if relative_error <= self.threshold:
                correct += 1
        return round((correct / len(actual)) * 100, 2)
    
    def _calculate_mae(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """평균 절대 오차 (Mean Absolute Error)"""
        return float(np.mean(np.abs(predicted - actual)))
    
    def _calculate_mse(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """평균 제곱 오차 (Mean Squared Error)"""
        return float(np.mean((predicted - actual) ** 2))
    
    def _calculate_rmse(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """제곱근 평균 제곱 오차 (Root Mean Squared Error)"""
        return float(np.sqrt(self._calculate_mse(actual, predicted)))
    
    def _calculate_mape(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """평균 절대 백분율 오차 (Mean Absolute Percentage Error)"""
        # 0으로 나누기 방지
        non_zero_mask = actual != 0
        if not np.any(non_zero_mask):
            return float('inf')
        
        mape = np.mean(np.abs((actual[non_zero_mask] - predicted[non_zero_mask]) 
                             / actual[non_zero_mask])) * 100
        return float(mape)
    
    def _calculate_r_squared(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """결정 계수 (R-squared)"""
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        
        if ss_tot == 0:
            return 1.0 if ss_res == 0 else 0.0
        
        return float(1 - (ss_res / ss_tot))
    
    def _calculate_mean_error(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """평균 오차 (편향)"""
        return float(np.mean(predicted - actual))
    
    def _calculate_std_error(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """오차의 표준편차"""
        errors = predicted - actual
        return float(np.std(errors))
    
    def get_performance_summary(self, metrics: Dict[str, Any]) -> str:
        """성능 요약 문자열 생성"""
        if "error" in metrics:
            return f"평가 오류: {metrics['error']}"
        
        summary = f"""
=== 모델 성능 평가 결과 ===
샘플 수: {metrics['num_samples']}개
임계값: {metrics['threshold'] * 100}%

=== 정확도 지표 ===
• 정확도 (Accuracy): {metrics['accuracy']}%
• 정확한 예측: {metrics['correct_predictions']}개
• 부정확한 예측: {metrics['incorrect_predictions']}개

=== 회귀 평가 지표 ===
• MAE (평균 절대 오차): {metrics['mae']:.4f}
• MSE (평균 제곱 오차): {metrics['mse']:.4f}
• RMSE (제곱근 평균 제곱 오차): {metrics['rmse']:.4f}
• MAPE (평균 절대 백분율 오차): {metrics['mape']:.2f}%
• R² (결정 계수): {metrics['r_squared']:.4f}

=== 오차 분석 ===
• 평균 오차 (편향): {metrics['mean_error']:.4f}
• 오차 표준편차: {metrics['std_error']:.4f}
        """
        return summary.strip()
    
    def set_threshold(self, new_threshold: float) -> None:
        """정확도 판정 임계값 변경"""
        self.threshold = new_threshold
        logging.info(f"임계값 변경: {new_threshold}") 