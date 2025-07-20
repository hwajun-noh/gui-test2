# config/settings_manager.py
from PyQt5.QtCore import QSettings

class SettingsManager:
    def __init__(self, company_name, app_name):
        # 여기서 QSettings를 초기화
        # => 사용자의 OS별로 레지스트리나 .conf(ini) 파일 등에 저장됩니다.
        self._settings = QSettings(company_name, app_name)

    def save(self, section_key, sub_key, value):
        """
        예: save("AllTabTable", "column_widths", [100, 200, 300])
        => 최종 'AllTabTable/column_widths' 라는 경로에 [100,200,300] 저장
        """
        self._settings.setValue(f"{section_key}/{sub_key}", value)

    def load(self, section_key, sub_key, default_value=None):
        """
        예: load("AllTabTable", "column_widths", [])
        => 'AllTabTable/column_widths'에서 값을 가져옴
        """
        return self._settings.value(f"{section_key}/{sub_key}", default_value)