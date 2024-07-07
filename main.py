import sys
import os
import json
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QFileDialog, QProgressBar, QComboBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtGui import QIcon  # QIcon 클래스 추가

from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS, GPSTAGS
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

class ImageProcessor(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(self, input_folder, output_folder, font_path, font_size):
        super().__init__()
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.font_path = font_path
        self.font_size = font_size

    def run(self):
        processed_images = []
        image_files = [f for f in os.listdir(self.input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        total_files = len(image_files)

        for i, filename in enumerate(image_files):
            input_path = os.path.join(self.input_folder, filename)
            output_path = os.path.join(self.output_folder, filename)

            try:
                self.process_image(input_path, output_path)
                processed_images.append(output_path)
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")

            self.progress.emit(int((i + 1) / total_files * 100))

        self.finished.emit(processed_images)

    def get_exif_data(self, image):
        exif_data = {}
        try:
            info = image._getexif()
            if info:
                for tag_id, value in info.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "GPSInfo":
                        gps_data = {}
                        for t in value:
                            sub_tag = GPSTAGS.get(t, t)
                            gps_data[sub_tag] = value[t]
                        exif_data[tag] = gps_data
                    else:
                        exif_data[tag] = value
        except Exception as e:
            print(f"Error getting EXIF data: {str(e)}")
        return exif_data

    def get_decimal_coordinates(self, info):
        try:
            for key in ['Latitude', 'Longitude']:
                if 'GPS'+key in info and 'GPS'+key+'Ref' in info:
                    e = info['GPS'+key]
                    ref = info['GPS'+key+'Ref']
                    info[key] = ( self.convert_to_degrees(e[0]) +
                                  self.convert_to_degrees(e[1]) / 60 +
                                  self.convert_to_degrees(e[2]) / 3600
                                ) * (-1 if ref in ['S','W'] else 1)
            if 'Latitude' in info and 'Longitude' in info:
                return [info['Latitude'], info['Longitude']]
        except Exception as e:
            print(f"Error getting decimal coordinates: {str(e)}")
        return None

    def convert_to_degrees(self, value):
        if isinstance(value, tuple):
            return float(value[0]) / float(value[1])
        return float(value)

    def get_address(self, gps_coords):
        if gps_coords is None:
            return " "  # GPS 좌표가 없는 경우 빈 문자열 반환
        geolocator = Nominatim(user_agent="my_agent")
        try:
            location = geolocator.reverse(f"{gps_coords[0]}, {gps_coords[1]}")
            if location:
                address = location.raw['address']
                # print(address)
                province = address.get('province', '')
                city = address.get('city', '')
                town = address.get('town', '')
                
                # city나 town 중 하나라도 있으면 반환
                if city or town:
                    if province:
                        return f"{province} {city}".strip()
                    else:    
                        return f"{city} {town}".strip()
                
                # city와 town이 없는 경우 다른 관련 필드 확인
                village = address.get('village', '')
                suburb = address.get('suburb', '')
                
                if village or suburb:
                    return f"{village} {suburb}".strip()
                
                # 모든 정보가 없는 경우
                return " "
            else:
                return " "
        except GeocoderTimedOut:
            return " "
        except Exception as e:
            print(f"Error getting address: {str(e)}")
            return " "

    def process_image(self, input_path, output_path):
        with Image.open(input_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')


            
            img_width, img_height = img.size
            base_font_size = int(min(img_width, img_height) * 0.05)  # 이미지 크기의 5%를 기본 폰트 크기로 설정
            
            time_font = ImageFont.truetype(self.font_path, base_font_size)
            date_font = ImageFont.truetype(self.font_path, int(base_font_size * 0.8))
            small_font = ImageFont.truetype(self.font_path, int(base_font_size * 0.7))
            address_font = ImageFont.truetype(self.font_path, int(base_font_size * 0.7))

            exif_data = self.get_exif_data(img)


            # Orientation 값에 따라 이미지 회전 또는 반전
            orientation = exif_data.get('Orientation', 1)

            if orientation == 6:  # 90도 회전
                img = img.transpose(Image.ROTATE_270)
            elif orientation == 8:  # 270도 회전
                img = img.transpose(Image.ROTATE_90)
            elif orientation == 3:  # 180도 회전
                img = img.transpose(Image.ROTATE_180)
            elif orientation == 2:  # 좌우 반전
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 4:  # 상하 반전 후 좌우 반전
                img = img.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 5:  # 좌우 반전 후 90도 회전
                img = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
            elif orientation == 7:  # 좌우 반전 후 270도 회전
                img = img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)

            date_taken = exif_data.get('DateTime', exif_data.get('DateTimeOriginal', datetime.now().strftime('%Y:%m:%d %H:%M:%S')))
            date_obj = datetime.strptime(date_taken, '%Y:%m:%d %H:%M:%S')
            
            weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            weekday = weekdays[date_obj.weekday()]
            
            gps_info = exif_data.get('GPSInfo', {})
            gps_coords = self.get_decimal_coordinates(gps_info)
            address = self.get_address(gps_coords)

            draw = ImageDraw.Draw(img)
            time_font = ImageFont.truetype(self.font_path, base_font_size)
            date_font = ImageFont.truetype(self.font_path, int(base_font_size * 0.4))  # 0.6에서 0.8로 증가
            weekday_font = ImageFont.truetype(self.font_path, int(base_font_size * 0.4))  # 0.5에서 0.7로 증가
            address_font = ImageFont.truetype(self.font_path, int(base_font_size * 0.6))
            
            time_text = f"{date_obj.strftime('%H:%M')}"
            date_text = f"{date_obj.strftime('%Y/%m/%d')}"
            weekday_text = f"{weekday}"
            
            img_width, img_height = img.size
            # margin = 20
            # line_spacing = int(self.font_size * 0.3)  # 줄 간격 증가
            margin = int(min(img_width, img_height) * 0.02)  # 이미지 크기의 2%를 마진으로 설정
            line_spacing = int(base_font_size * 0.3)  # 기본 폰트 크기의 30%를 줄 간격으로 설정            
            
            # 시간 텍스트 위치 계산
            time_bbox = draw.textbbox((0, 0), time_text, font=time_font)
            time_width = time_bbox[2] - time_bbox[0]
            time_height = time_bbox[3] - time_bbox[1]
            time_x = margin
            time_y = img_height - time_height - margin * 2 - address_font.size - line_spacing * 2
            
            # 노란색 바 추가 (더 길게)
            bar_width = int(time_height * 0.2)
            bar_x = time_x + time_width + margin
            bar_y = time_y
            #bar_height = time_height + small_font.size + line_spacing  # 바 길이 증가
            bar_height = time_height * 1.3
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill=(255, 255, 0))
            
            # 날짜 텍스트 위치 계산
            date_x = bar_x + bar_width + margin
            date_y = time_y
            
            # 요일 텍스트 위치 계산
            weekday_x = date_x
            weekday_y = date_y + date_font.size + line_spacing * 0.5
            
            # 주소 텍스트 위치 계산 (간격 증가)
            address_y = time_y + time_height + line_spacing * 2
            
            # 텍스트 그리기
            draw.text((time_x, time_y), time_text, font=time_font, fill=(255, 255, 255))
            draw.text((date_x, date_y), date_text, font=date_font, fill=(255, 255, 255))
            draw.text((weekday_x, weekday_y), weekday_text, font=weekday_font, fill=(255, 255, 255))
            draw.text((margin, address_y), address, font=address_font, fill=(255, 255, 255))

            img.save(output_path, quality=95, subsampling=0)


class ImageProcessorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_file = "settings.json"  # 설정 파일 이름
        self.load_settings()  # 설정 불러오기

        # 아이콘 설정
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.ico")
        self.setWindowIcon(QIcon(icon_path))  # 아이콘 설정

        self.initUI()

    def initUI(self):
        self.setWindowTitle('타임스탬퍼-배치')  # 타이틀 변경
        self.setGeometry(300, 300, 500, 200)

        layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        input_button = QPushButton('입력 폴더 선택')
        input_button.clicked.connect(self.select_input_folder)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(input_button)

        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        output_button = QPushButton('출력 폴더 선택')
        output_button.clicked.connect(self.select_output_folder)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(output_button)

        # 폰트 드롭다운 목록 추가
        font_layout = QHBoxLayout()
        self.font_combo = QComboBox()
        self.load_fonts()
        font_layout.addWidget(QLabel('폰트:'))
        font_layout.addWidget(self.font_combo)

        process_button = QPushButton('처리 시작')
        process_button.clicked.connect(self.start_processing)

        self.progress_bar = QProgressBar()
        self.result_label = QLabel()

        layout.addLayout(input_layout)
        layout.addLayout(output_layout)
        layout.addLayout(font_layout)  # 폰트 레이아웃 추가
        layout.addWidget(process_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.result_label)

        self.setLayout(layout)

        # 설정 값으로 초기화
        self.input_edit.setText(self.settings.get("input_folder", ""))
        self.output_edit.setText(self.settings.get("output_folder", ""))
        self.font_combo.setCurrentText(self.settings.get("font", ""))

    def load_fonts(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_dir = os.path.join(script_dir, "fonts")

        if os.path.exists(font_dir):
            font_files = [f for f in os.listdir(font_dir) if f.lower().endswith(('.ttf', '.otf', '.ttc'))]
            for font_file in font_files:
                self.font_combo.addItem(font_file)
        else:
            self.result_label.setText("fonts 폴더를 찾을 수 없습니다.")

    def save_settings(self):
        self.settings["input_folder"] = self.input_edit.text()
        self.settings["output_folder"] = self.output_edit.text()
        self.settings["font"] = self.font_combo.currentText()
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f)

    def load_settings(self):
        try:
            with open(self.settings_file, "r") as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            self.settings = {}

    def select_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "입력 폴더 선택")
        self.input_edit.setText(folder)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "출력 폴더 선택")
        self.output_edit.setText(folder)

    def start_processing(self):
        input_folder = self.input_edit.text()
        output_folder = self.output_edit.text()

        if not input_folder or not output_folder:
            self.result_label.setText("입력 및 출력 폴더를 모두 선택해주세요.")
            return

        # 선택된 폰트 파일 이름 가져오기
        font_filename = self.font_combo.currentText()
        font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", font_filename)

        # 폰트 크기 고정
        font_size = 200


        self.save_settings()  # 설정 저장
        self.processor = ImageProcessor(input_folder, output_folder, font_path, font_size)
        self.processor.progress.connect(self.update_progress)
        self.processor.finished.connect(self.process_finished)
        self.processor.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def process_finished(self, processed_images):
        self.result_label.setText(f"처리 완료: {len(processed_images)}개 이미지")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ImageProcessorApp()
    ex.show()
    sys.exit(app.exec_())
