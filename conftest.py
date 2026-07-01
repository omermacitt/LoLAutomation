"""pytest kök konfigürasyonu — repo kökünü import yoluna ekler (düz modül import'ları için)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
