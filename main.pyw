# Copyright (C) 2026  KOREAHS
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QLabel,
                             QStackedWidget, QProgressBar, QMessageBox, QFileDialog, QDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QStandardPaths
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

download_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("로블록스 로그인")
        self.resize(800, 600)
        self.cookie_value = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.webview = QWebEngineView()
        layout.addWidget(self.webview)
        
        # Intercept cookies
        self.profile = QWebEngineProfile.defaultProfile()
        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self.on_cookie_added)
        
        self.webview.load(QUrl("https://www.roblox.com/login"))
        
    def on_cookie_added(self, cookie):
        name = bytearray(cookie.name()).decode()
        if name == ".ROBLOSECURITY":
            self.cookie_value = bytearray(cookie.value()).decode()
            self.accept()

class AssetFetchWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bytes)
    error = pyqtSignal(str)

    def __init__(self, asset_id, cookie=None):
        super().__init__()
        self.asset_id = asset_id
        self.cookie = cookie

    def run(self):
        try:
            self.progress.emit("에셋 정보 조회 중...", 10)
            url = f"https://assetdelivery.roblox.com/v2/assetid/{self.asset_id}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            cookies = {'.ROBLOSECURITY': self.cookie} if self.cookie else {}
            
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            
            if response.status_code != 200:
                self.error.emit(f"에셋 정보를 가져오지 못했습니다. 상태 코드: {response.status_code}")
                return
            
            data = response.json()
            
            # assetTypeId check. Some responses might have it in an array or single object
            if isinstance(data, list):
                if len(data) == 0:
                    self.error.emit("에셋 정보가 비어있습니다.")
                    return
                asset_data = data[0]
            else:
                asset_data = data
                
            asset_type_id = asset_data.get('assetTypeId')
            if asset_type_id != 1:
                self.error.emit("이미지 에셋이 아닙니다")
                return

            self.progress.emit("에셋 위치 확인 중...", 30)
            locations = asset_data.get('locations')
            if not locations or len(locations) == 0:
                self.error.emit("에셋 위치(location) 정보를 찾을 수 없습니다.")
                return
                
            location_url = locations[0].get('location')
            if not location_url:
                self.error.emit("location URL이 비어있습니다.")
                return

            self.progress.emit("이미지 다운로드 중...", 50)
            img_response = requests.get(location_url, timeout=15)
            
            if img_response.status_code != 200:
                self.error.emit(f"이미지 다운로드 실패. 상태 코드: {img_response.status_code}")
                return
            
            self.progress.emit("다운로드 완료!", 100)
            self.finished.emit(img_response.content)

        except Exception as e:
            self.error.emit(f"오류가 발생했습니다: {str(e)}")

class RobloxAssetExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Roblox Image Extractor")
        self.resize(500, 500)
        
        self.image_data = None
        self.cookie = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        self._init_input_page()
        self._init_loading_page()
        self._init_result_page()
        
        self.stacked_widget.setCurrentIndex(0)

    def _init_input_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        layout.addStretch(1)
        
        title = QLabel("Roblox 이미지 추출기")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)
        
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("에셋 ID를 입력하세요 (예: 1234567)")
        self.id_input.setStyleSheet("padding: 8px; font-size: 14px;")
        self.id_input.returnPressed.connect(self.start_fetch)
        layout.addWidget(self.id_input)
        
        btn_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("로블록스 로그인")
        self.login_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #f39c12; color: white; border-radius: 5px;")
        self.login_btn.clicked.connect(self.open_login)
        btn_layout.addWidget(self.login_btn)

        self.open_login()

        fetch_btn = QPushButton("가져오기")
        fetch_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #007bff; color: white; border-radius: 5px;")
        fetch_btn.clicked.connect(self.start_fetch)
        btn_layout.addWidget(fetch_btn)
        
        layout.addLayout(btn_layout)

        announceTextLayout = QHBoxLayout()
        announceTextLabel = QLabel("이 앱은 Roblox에서 제공하는 공식 앱이 아닙니다. Roblox의 이용 약관을 준수하시기 바랍니다.\n이 앱은 사용자의 개인정보 (쿠키 등)을 Roblox를 제외한 다른 곳에 보내지 않습니다.\n 타인의 에셋을 내려받을 경우에는 저작권을 준수하시기 바랍니다.\n 이 앱의 제작자는 일체의 법적 책임을 지지 않으며, 법적 책임은 모두 사용자에게 있습니다.\nBy KOREAHS")
        announceTextLabel.setStyleSheet("font-size: 11px; color: gray;")
        announceTextLayout.addWidget(announceTextLabel)
        announceTextLabel.setAlignment(Qt.AlignCenter)
        announceTextLabel.setWordWrap(True)

        layout.addLayout(announceTextLayout)
        
        layout.addStretch(1)
        self.stacked_widget.addWidget(page) # Index 0

    def open_login(self):
        dialog = LoginDialog(self)
        if dialog.exec_() and dialog.cookie_value:
            self.cookie = dialog.cookie_value
            self.login_btn.setText("로그인 완료")
            self.login_btn.setEnabled(False)
            self.login_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #28a745; color: white; border-radius: 5px;")
            QMessageBox.information(self, "성공", "로그인 쿠키를 성공적으로 가져왔습니다!")

    def _init_loading_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        
        self.status_label = QLabel("준비 중...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch(1)
        self.stacked_widget.addWidget(page) # Index 1

    def _init_result_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        self.image_preview = QLabel("이미지 미리보기")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.image_preview.setMinimumSize(400, 400)
        layout.addWidget(self.image_preview, 1) # Give it stretch
        
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("저장하기")
        self.save_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #28a745; color: white; border-radius: 5px;")
        self.save_btn.clicked.connect(self.save_image)
        btn_layout.addWidget(self.save_btn)
        
        self.back_btn = QPushButton("초기 화면으로")
        self.back_btn.setStyleSheet("padding: 10px; font-size: 14px; background-color: #6c757d; color: white; border-radius: 5px;")
        self.back_btn.clicked.connect(self.go_to_input)
        btn_layout.addWidget(self.back_btn)
        
        layout.addLayout(btn_layout)
        self.stacked_widget.addWidget(page) # Index 2

    def start_fetch(self):
        asset_id = self.id_input.text().strip()
        self.asset_id = asset_id
        if not asset_id:
            QMessageBox.warning(self, "경고", "에셋 ID를 입력해주세요.")
            return
            
        if not asset_id.isdigit():
            QMessageBox.warning(self, "경고", "숫자로 된 에셋 ID를 입력해주세요.")
            return

        self.stacked_widget.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.status_label.setText("작업 시작...")
        
        self.worker = AssetFetchWorker(asset_id, self.cookie)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_fetch_success)
        self.worker.error.connect(self.on_fetch_error)
        self.worker.start()

    def update_progress(self, status, value):
        self.status_label.setText(status)
        self.progress_bar.setValue(value)

    def on_fetch_success(self, image_bytes):
        self.image_data = image_bytes
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)
        
        if pixmap.isNull():
            self.on_fetch_error("유효한 이미지 데이터가 아닙니다.")
            return
            
        # Scale to fit while keeping aspect ratio
        scaled_pixmap = pixmap.scaled(self.image_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_preview.setPixmap(scaled_pixmap)
        
        self.stacked_widget.setCurrentIndex(2)

    def on_fetch_error(self, error_msg):
        QMessageBox.critical(self, "오류", error_msg)
        self.go_to_input()

    def go_to_input(self):
        self.id_input.clear()
        self.image_data = None
        self.stacked_widget.setCurrentIndex(0)
        
    def save_image(self):
        if not self.image_data:
            return
            
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "이미지 저장", f"{download_path}/roblox_asset_{self.asset_id}.png", 
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)", 
            options=options
        )
        
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(self.image_data)
                QMessageBox.information(self, "저장 완료", f"이미지가 성공적으로 저장되었습니다.\n{file_path}")
                # 저장 후 자동으로 초기 화면으로 돌아가기
                self.go_to_input()
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 중 오류가 발생했습니다: {str(e)}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Resize image if result page is active
        if self.stacked_widget.currentIndex() == 2 and self.image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(self.image_data)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.image_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set default style for a better look
    app.setStyle('Fusion')
    
    window = RobloxAssetExtractor()
    window.show()
    sys.exit(app.exec_())
