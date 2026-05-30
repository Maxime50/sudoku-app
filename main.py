"""
Sudoku — Application Android (Kivy)
- Grille pleine taille et centrée
- Boutons en symboles/icônes au lieu de mots
- Astuces intelligentes limitées à 2 par partie
"""

import json
import os
import random
import copy
import time

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import (NumericProperty, BooleanProperty,
                             ListProperty, ObjectProperty)
from kivy.utils import get_color_from_hex as hex_to_rgba, platform
from kivy.metrics import dp


if platform != 'android':
    Window.size = (420, 820)


# ============================================================
#  THEME
# ============================================================
class T:
    BG = hex_to_rgba('#F8F9FD') # Fond plus clair
    CARD = hex_to_rgba('#FFFFFF')
    GRID_BORDER = hex_to_rgba('#212A3E') # Bordure grille foncée
    GRID_LINE = hex_to_rgba('#D4D9E2') # Lignes internes discrètes
    CELL_BG = hex_to_rgba('#FFFFFF')
    CELL_RELATED = hex_to_rgba('#EBF0F8') # Ligne/colonne (très clair)
    CELL_SAME_NUM = hex_to_rgba('#C5D4F0') # Chiffres identiques mis en évidence
    CELL_SELECTED = hex_to_rgba('#A4BEF3') # Case sélectionnée
    CELL_HINT = hex_to_rgba('#FFE89C')
    TEXT_DARK = hex_to_rgba('#212A3E')
    TEXT_USER = hex_to_rgba('#3A6DDF') # Chiffres utilisateur en bleu franc
    TEXT_NOTE = hex_to_rgba('#8A95A5')
    TEXT_ERROR = hex_to_rgba('#E53E3E')
    TEXT_LIGHT = hex_to_rgba('#FFFFFF')
    TEXT_MUTED = hex_to_rgba('#8A95A5')
    TEXT_GREY = hex_to_rgba('#C0C7D5')
    PRIMARY = hex_to_rgba('#3A6DDF')
    DANGER = hex_to_rgba('#E53E3E')
    SUCCESS = hex_to_rgba('#2EB67D')
    WARNING = hex_to_rgba('#F2A516')
    NAV_INACTIVE = hex_to_rgba('#B4BCCC')
    NAV_ACTIVE = hex_to_rgba('#3A6DDF')
    DIFF_COLORS = {
        'Facile': hex_to_rgba('#2EB67D'),
        'Moyen': hex_to_rgba('#3A6DDF'),
        'Difficile': hex_to_rgba('#F2A516'),
        'Expert': hex_to_rgba('#E53E3E'),
    }
# ============================================================
#  PERSISTANCE
# ============================================================
def _storage_dir():
    try:
        from android.storage import app_storage_path
        return app_storage_path()
    except Exception:
        return os.path.expanduser('~')


STORAGE = _storage_dir()
SAVE_FILE = os.path.join(STORAGE, 'sudoku_save.json')
STATS_FILE = os.path.join(STORAGE, 'sudoku_stats.json')


def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def default_stats():
    return {
        d: {'played': 0, 'won': 0, 'won_no_err': 0,
            'total_time': 0, 'best_time': None}
        for d in ('Facile', 'Moyen', 'Difficile', 'Expert')
    }


# ============================================================
#  GÉNÉRATEUR
# ============================================================
class SudokuGenerator:
    def is_valid(self, g, r, c, n):
        for x in range(9):
            if g[r][x] == n or g[x][c] == n:
                return False
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for i in range(3):
            for j in range(3):
                if g[br + i][bc + j] == n:
                    return False
        return True

    def fill(self, g):
        for i in range(81):
            r, c = i // 9, i % 9
            if g[r][c] == 0:
                nums = list(range(1, 10))
                random.shuffle(nums)
                for n in nums:
                    if self.is_valid(g, r, c, n):
                        g[r][c] = n
                        if self._full(g) or self.fill(g):
                            return True
                        g[r][c] = 0
                return False
        return True

    def _full(self, g):
        return all(g[i][j] != 0 for i in range(9) for j in range(9))

    def count(self, g, limit=2):
        for i in range(81):
            r, c = i // 9, i % 9
            if g[r][c] == 0:
                t = 0
                for n in range(1, 10):
                    if self.is_valid(g, r, c, n):
                        g[r][c] = n
                        t += self.count(g, limit)
                        g[r][c] = 0
                        if t >= limit:
                            return t
                return t
        return 1

    def generate(self, difficulty):
        g = [[0] * 9 for _ in range(9)]
        self.fill(g)
        # Remplacement de copy.deepcopy() par une copie de liste ultra-rapide
        solution = [row[:] for row in g] 
        target = {'Facile': 35, 'Moyen': 45, 'Difficile': 52, 'Expert': 58}[difficulty]
        cells = [(i, j) for i in range(9) for j in range(9)]
        random.shuffle(cells)
        removed = 0
        for (r, c) in cells:
            if removed >= target: break
            backup = g[r][c]
            g[r][c] = 0
            if self.count([row[:] for row in g]) != 1:
                g[r][c] = backup
            else:
                removed += 1
        return [row[:] for row in g], solution


# ============================================================
#  ANALYSEUR D'ASTUCES INTELLIGENT
# ============================================================
class HintFinder:
    """Trouve une astuce intelligente avec explication pédagogique"""

    @staticmethod
    def candidates(current, r, c):
        """Retourne l'ensemble des chiffres possibles pour la case (r,c)"""
        if current[r][c] != 0:
            return set()
        used = set()
        for x in range(9):
            used.add(current[r][x])
            used.add(current[x][c])
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for i in range(3):
            for j in range(3):
                used.add(current[br + i][bc + j])
        return set(range(1, 10)) - used

    @staticmethod
    def find_hint(puzzle, current, solution):
        """
        Trouve une bonne astuce. Retourne (row, col, num, explanation) ou None.

        Stratégies par ordre de qualité:
        1. Case avec un seul candidat possible (singleton naked)
        2. Chiffre qui ne peut aller qu'à une seule place dans une ligne
        3. Chiffre qui ne peut aller qu'à une seule place dans une colonne
        4. Chiffre qui ne peut aller qu'à une seule place dans un bloc 3x3
        5. Sinon une case aléatoire vide
        """
        # Stratégie 1 : naked singleton (case avec un seul candidat)
        for r in range(9):
            for c in range(9):
                if current[r][c] == 0:
                    cands = HintFinder.candidates(current, r, c)
                    if len(cands) == 1:
                        num = cands.pop()
                        if num == solution[r][c]:
                            return (r, c, num,
                                    f"Cette case (ligne {r+1}, colonne {c+1}) n'a qu'une seule valeur possible : {num}.\n\n"
                                    f"En regardant sa ligne, sa colonne et son carre 3x3, tous les autres chiffres sont deja utilises.")

        # Stratégie 2 : hidden singleton dans une ligne
        for r in range(9):
            for n in range(1, 10):
                # Chercher où n peut aller dans cette ligne
                possible = []
                for c in range(9):
                    if current[r][c] == 0 and n in HintFinder.candidates(current, r, c):
                        possible.append(c)
                if len(possible) == 1:
                    c = possible[0]
                    if n == solution[r][c]:
                        return (r, c, n,
                                f"Le chiffre {n} ne peut aller qu'en colonne {c+1} dans la ligne {r+1}.\n\n"
                                f"Toutes les autres cases vides de cette ligne ne peuvent pas contenir {n} a cause des contraintes de leurs colonnes ou blocs.")

        # Stratégie 3 : hidden singleton dans une colonne
        for c in range(9):
            for n in range(1, 10):
                possible = []
                for r in range(9):
                    if current[r][c] == 0 and n in HintFinder.candidates(current, r, c):
                        possible.append(r)
                if len(possible) == 1:
                    r = possible[0]
                    if n == solution[r][c]:
                        return (r, c, n,
                                f"Le chiffre {n} ne peut aller qu'en ligne {r+1} dans la colonne {c+1}.\n\n"
                                f"Toutes les autres cases vides de cette colonne ne peuvent pas contenir {n} a cause des contraintes de leurs lignes ou blocs.")

        # Stratégie 4 : hidden singleton dans un bloc 3x3
        for br in range(0, 9, 3):
            for bc in range(0, 9, 3):
                for n in range(1, 10):
                    possible = []
                    for i in range(3):
                        for j in range(3):
                            r, c = br + i, bc + j
                            if current[r][c] == 0 and n in HintFinder.candidates(current, r, c):
                                possible.append((r, c))
                    if len(possible) == 1:
                        r, c = possible[0]
                        if n == solution[r][c]:
                            block_num = (br // 3) * 3 + (bc // 3) + 1
                            return (r, c, n,
                                    f"Dans le carre 3x3 numero {block_num} (en haut a gauche : ligne {br+1}-{br+3}, colonne {bc+1}-{bc+3}), le chiffre {n} ne peut aller qu'en ligne {r+1}, colonne {c+1}.\n\n"
                                    f"Les autres cases vides du carre ne peuvent pas contenir {n}.")

        # Fallback : une case avec peu de candidats
        best = None
        best_cands = 10
        for r in range(9):
            for c in range(9):
                if current[r][c] == 0 and current[r][c] != solution[r][c]:
                    cands = HintFinder.candidates(current, r, c)
                    if 0 < len(cands) < best_cands:
                        best = (r, c)
                        best_cands = len(cands)
        if best:
            r, c = best
            num = solution[r][c]
            return (r, c, num,
                    f"La case ligne {r+1}, colonne {c+1} doit contenir {num}.\n\n"
                    f"Il y a {best_cands} candidats possibles pour cette case, et la deduction logique permet de trouver {num}.")

        # Vraiment rien trouvé : prendre une case vide
        for r in range(9):
            for c in range(9):
                if current[r][c] == 0:
                    num = solution[r][c]
                    return (r, c, num,
                            f"Essayez de placer {num} en ligne {r+1}, colonne {c+1}.")

        return None


# ============================================================
#  WIDGETS
# ============================================================
class FlatButton(Button):
    bg_color = ListProperty(T.CARD)
    border_color = ListProperty([0, 0, 0, 0])
    text_color = ListProperty(T.TEXT_DARK)
    radius = NumericProperty(dp(10))

    def __init__(self, **kwargs):
        kwargs.setdefault('background_color', (0, 0, 0, 0))
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('color', T.TEXT_DARK)
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg = Color(*self.bg_color)
            self._rect = RoundedRectangle(
                pos=self.pos, size=self.size,
                radius=[(self.radius, self.radius)] * 4)
            self._border = Color(*self.border_color)
            self._line = Line(
                rounded_rectangle=(self.x, self.y,
                                   self.width, self.height, self.radius),
                width=1.2)
        self.color = self.text_color
        self.bind(pos=self._update, size=self._update,
                  bg_color=self._update_colors,
                  border_color=self._update_colors,
                  text_color=self._update_text_color,
                  radius=self._update)

    def _update(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [(self.radius, self.radius)] * 4
        self._line.rounded_rectangle = (
            self.x, self.y, self.width, self.height, self.radius)

    def _update_colors(self, *a):
        self._bg.rgba = self.bg_color
        self._border.rgba = self.border_color

    def _update_text_color(self, *a):
        self.color = self.text_color


class Card(BoxLayout):
    bg_color = ListProperty(T.CARD)
    border_color = ListProperty(T.GRID_LINE)
    radius = NumericProperty(dp(10))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg = Color(*self.bg_color)
            self._rect = RoundedRectangle(
                pos=self.pos, size=self.size,
                radius=[(self.radius, self.radius)] * 4)
            self._border = Color(*self.border_color)
            self._line = Line(
                rounded_rectangle=(self.x, self.y,
                                   self.width, self.height, self.radius),
                width=1.2)
        self.bind(pos=self._update, size=self._update,
                  bg_color=self._update_colors,
                  border_color=self._update_colors)

    def _update(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [(self.radius, self.radius)] * 4
        self._line.rounded_rectangle = (
            self.x, self.y, self.width, self.height, self.radius)

    def _update_colors(self, *a):
        self._bg.rgba = self.bg_color
        self._border.rgba = self.border_color


# ============================================================
#  GRILLE SUDOKU
# ============================================================
class SudokuGrid(Widget):
    def __init__(self, game_screen, **kwargs):
        super().__init__(**kwargs)
        self.game = game_screen
        self.labels = {}
        
        for r in range(9):
            for c in range(9):
                lbl = Label(markup=True, halign='center', valign='middle')
                self.add_widget(lbl)
                self.labels[(r, c)] = lbl
                
        self.bind(pos=self._redraw, size=self._redraw)

    @property
    def cell_size(self):
        return min(self.width, self.height) / 9.0

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos): return False
        if self.game.paused or self.game.game_over: return True
        cs = self.cell_size
        if cs <= 0: return True
        col = int((touch.x - self.x) // cs)
        row = 8 - int((touch.y - self.y) // cs)
        if 0 <= row < 9 and 0 <= col < 9:
            self.game.on_cell_clicked(row, col)
        return True

    def _redraw(self, *a):
        self.canvas.before.clear()
        if not getattr(self.game, 'puzzle', None): return
        
        cs = self.cell_size
        if cs <= 0: return # Protection vitale contre les crashs graphiques
        
        x0, y0 = self.x, self.y
        grid_size = cs * 9

        with self.canvas.before:
            if self.game.paused:
                Color(*hex_to_rgba('#E1E6F0'))
                Rectangle(pos=(x0, y0), size=(grid_size, grid_size))
            else:
                for r in range(9):
                    for c in range(9):
                        bg = self.game._cell_bg(r, c)
                        Color(*bg)
                        Rectangle(pos=(x0 + c * cs, y0 + (8 - r) * cs), size=(cs, cs))

                for i in range(10):
                    if i % 3 == 0:
                        Color(*T.GRID_BORDER)
                        width = 1.8
                    else:
                        Color(*T.GRID_LINE)
                        width = 1.0
                    Line(points=[x0, y0 + i * cs, x0 + grid_size, y0 + i * cs], width=width)
                    Line(points=[x0 + i * cs, y0, x0 + i * cs, y0 + grid_size], width=width)

        if self.game.paused:
            for lbl in self.labels.values(): 
                if lbl.text != "": lbl.text = ""
            return

        def to_hex(c):
            return '{:02x}{:02x}{:02x}'.format(int(c[0]*255), int(c[1]*255), int(c[2]*255))
        
        note_color = to_hex(T.TEXT_NOTE)
        prim_color = to_hex(T.PRIMARY)

        for r in range(9):
            for c in range(9):
                lbl = self.labels[(r, c)]
                
                # Ne mettre à jour QUE si ça a changé (Évite de saturer la RAM)
                new_pos = (x0 + c * cs, y0 + (8 - r) * cs)
                new_size = (cs, cs)
                if lbl.pos != new_pos: lbl.pos = new_pos
                if lbl.size != new_size: 
                    lbl.size = new_size
                    lbl.text_size = new_size

                v = self.game.current[r][c]
                if v != 0:
                    col = T.TEXT_ERROR if (r, c) in self.game.error_cells else (T.TEXT_DARK if self.game.puzzle[r][c] != 0 else T.TEXT_USER)
                    if lbl.color != col: lbl.color = col
                    
                    font_s = max(1, cs * 0.55)
                    if lbl.font_size != font_s: lbl.font_size = font_s
                    
                    new_text = f'[b]{v}[/b]'
                    if lbl.text != new_text: lbl.text = new_text
                    
                elif self.game.notes[r][c]:
                    white = [1,1,1,1]
                    if lbl.color != white: lbl.color = white
                    
                    font_s = max(1, cs * 0.22)
                    if lbl.font_size != font_s: lbl.font_size = font_s
                    
                    n_str = ""
                    for nr in range(3):
                        for nc in range(3):
                            n = nr * 3 + nc + 1
                            if n in self.game.notes[r][c]:
                                c_hex = prim_color if self.game.selected_value == n else note_color
                                bold = "[b]" if self.game.selected_value == n else ""
                                bold_end = "[/b]" if self.game.selected_value == n else ""
                                n_str += f"[color=#{c_hex}]{bold}{n}{bold_end}[/color]"
                            else:
                                n_str += " "
                            if nc < 2: n_str += "   "
                        if nr < 2: n_str += "\n"
                    if lbl.text != n_str: lbl.text = n_str
                else:
                    if lbl.text != "": lbl.text = ""
                      
# ============================================================
#  BOUTON CHIFFRE
# ============================================================
class NumberButton(ButtonBehavior, Widget):
    num = NumericProperty(1)
    count_left = NumericProperty(9)
    is_active = BooleanProperty(False)

    def __init__(self, num, game, **kwargs):
        super().__init__(**kwargs)
        self.num = num
        self.game = game
        
        self.lbl = Label(text=str(self.num), font_size=dp(38), halign='center', valign='middle')
        self.add_widget(self.lbl)
        
        self.bind(pos=self._update_lbl, size=self._update_lbl, 
                  is_active=self._update_colors, count_left=self._update_colors)
        Clock.schedule_once(self._update_lbl, 0)
        self._update_colors()

    def _update_lbl(self, *a):
        if self.lbl.pos != self.pos: self.lbl.pos = self.pos
        if self.lbl.size != self.size:
            self.lbl.size = self.size
            self.lbl.text_size = self.size

    def _update_colors(self, *a):
        new_color = T.PRIMARY if self.is_active or self.count_left > 0 else T.TEXT_GREY
        if self.lbl.color != new_color:
            self.lbl.color = new_color

    def on_release(self):
        self.game.on_number_tap(self.num)
      
# ============================================================
#  ÉCRAN DE JEU
# ============================================================
class GameScreen(BoxLayout):
    def __init__(self, app, difficulty, resume_data=None, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.difficulty = difficulty

        self.puzzle = None
        self.solution = None
        self.current = None
        self.notes = [[set() for _ in range(9)] for _ in range(9)]
        self.errors = 0
        self.max_errors = 3
        self.max_hints = 2
        self.hints_used = 0
        self.selected_cell = None
        self.selected_value = None
        self.notes_mode = False
        self.hold_mode = False
        self.hold_number = None
        self.history = []
        self.error_cells = set()
        self.paused = False
        self.start_time = None
        self.elapsed = 0
        self.game_over = False

        with self.canvas.before:
            Color(*T.BG)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self._build_ui()

        if resume_data:
            self._load_state(resume_data)
        else:
            Clock.schedule_once(lambda dt: self._generate_new(), 0.05)

        self._timer_event = Clock.schedule_interval(self._update_timer, 1.0)

    def cleanup(self):
        try:
            self._timer_event.cancel()
        except Exception:
            pass

    def _update_bg(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _fix_label(self, instance, value):
        instance.text_size = instance.size

    def _build_ui(self):
        # ====== En-tête (Top Bar) ======
        top = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(10), dp(6), dp(10), 0])
        
        # \uf053 = Chevron gauche FontAwesome
        back_btn = FlatButton(text='[font=fa-solid-900.ttf]\uf053[/font]', markup=True, font_size=dp(20), 
                              bg_color=(0,0,0,0), border_color=(0,0,0,0), text_color=T.TEXT_DARK, size_hint_x=None, width=dp(46))
        back_btn.bind(on_release=lambda b: self.go_home())
        top.add_widget(back_btn)
        
        top.add_widget(Widget()) # Espace vide au centre
        self.add_widget(top)

        # ====== Ligne d'infos (Facile, Erreur, Temps) ======
        info_row = BoxLayout(size_hint_y=None, height=dp(30), padding=[dp(20), 0])
        
        self.diff_label = Label(text=self.difficulty, font_size=dp(14), color=T.TEXT_MUTED, halign='left', valign='middle')
        self.diff_label.bind(size=lambda i, v: setattr(i, 'text_size', v))
        info_row.add_widget(self.diff_label)
        
        self.err_label = Label(text='Erreur: 0/3', font_size=dp(14), color=T.TEXT_MUTED, halign='center', valign='middle')
        self.err_label.bind(size=lambda i, v: setattr(i, 'text_size', v))
        info_row.add_widget(self.err_label)
        
        # Le timer fait office de bouton pause
        self.timer_btn = FlatButton(text='00:00 ||', font_size=dp(14), bg_color=(0,0,0,0), border_color=(0,0,0,0), text_color=T.TEXT_MUTED, halign='right', valign='middle')
        self.timer_btn.bind(on_release=lambda b: self.toggle_pause())
        self.timer_label = self.timer_btn
        info_row.add_widget(self.timer_btn)
        
        self.add_widget(info_row)

        # ====== Grille ======
        self.grid_anchor = AnchorLayout(anchor_x='center', anchor_y='center', padding=[dp(10), dp(10)])
        self.grid = SudokuGrid(self, size_hint=(None, None))
        self.grid_anchor.add_widget(self.grid)
        self.add_widget(self.grid_anchor)

        Window.bind(size=self._resize_grid)
        Clock.schedule_once(lambda dt: self._resize_grid(), 0.1)

        # ====== Boutons d'action (Sans bordures avec FontAwesome) ======
        # ====== Boutons d'action ======
        actions = BoxLayout(size_hint_y=None, height=dp(70), padding=[dp(10), dp(10)], spacing=dp(15))
        
        ic = int(dp(22)) # Taille de l'icône FontAwesome adaptée à l'écran
        tx = int(dp(11)) # Taille du texte adaptée à l'écran
        
        self.undo_btn = FlatButton(text=f'[font=fa-solid-900.ttf][size={ic}]\uf0e2[/size][/font]\n[size={tx}]Annuler[/size]', markup=True, halign='center', valign='middle', bg_color=[0,0,0,0], border_color=[0,0,0,0], text_color=T.TEXT_MUTED)
        self.undo_btn.bind(on_release=lambda b: self.undo())
        
        self.erase_btn = FlatButton(text=f'[font=fa-solid-900.ttf][size={ic}]\uf00d[/size][/font]\n[size={tx}]Effacer[/size]', markup=True, halign='center', valign='middle', bg_color=[0,0,0,0], border_color=[0,0,0,0], text_color=T.TEXT_MUTED)
        self.erase_btn.bind(on_release=lambda b: self.erase())
        
        self.notes_btn = FlatButton(text=f'[font=fa-solid-900.ttf][size={ic}]\uf303[/size][/font]\n[size={tx}]Notes OFF[/size]', markup=True, halign='center', valign='middle', bg_color=[0,0,0,0], border_color=[0,0,0,0], text_color=T.TEXT_MUTED)
        self.notes_btn.bind(on_release=lambda b: self.toggle_notes())
        
        self.hint_btn = FlatButton(text=f'[font=fa-solid-900.ttf][size={ic}]\uf0eb[/size][/font]\n[size={tx}]Astuce[/size]', markup=True, halign='center', valign='middle', bg_color=[0,0,0,0], border_color=[0,0,0,0], text_color=T.TEXT_MUTED)
        self.hint_btn.bind(on_release=lambda b: self.use_hint())
        
        for btn in [self.undo_btn, self.erase_btn, self.notes_btn, self.hint_btn]:
            actions.add_widget(btn)
        self.add_widget(actions)

        # ====== Pavé numérique ======
        nums = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(10), dp(5)], spacing=dp(5))
        self.num_buttons = {}
        for i in range(1, 10):
            wrap = NumberButton(num=i, game=self)
            nums.add_widget(wrap)
            self.num_buttons[i] = wrap
        self.add_widget(nums)

        self.hold_label = Label(text='', font_size=dp(10), color=T.WARNING, size_hint_y=None, height=dp(20), italic=True)
        self.add_widget(self.hold_label)
      
    def _resize_grid(self, *a):
        # Calculer la taille disponible pour la grille
        # Window.width - petit padding
        # Window.height - top bar (48) - actions (58) - nums (54) - hold (20) - padding
        ui_total = dp(48 + 58 + 54 + 20 + 16)
        available_w = Window.width - dp(16)
        available_h = Window.height - ui_total
        size = min(available_w, available_h)
        size = max(size, dp(280))
        cell = int(size / 9)
        size = cell * 9
        self.grid.size = (size, size)
        self.grid._redraw()

    def _generate_new(self):
        loading = LoadingPopup('Generation...')
        loading.open()

        def gen_then_continue(dt):
            self.puzzle, self.solution = SudokuGenerator().generate(self.difficulty)
            self.current = copy.deepcopy(self.puzzle)
            self.notes = [[set() for _ in range(9)] for _ in range(9)]
            self.start_time = time.time()
            self.elapsed = 0
            loading.dismiss()
            self._refresh_all()

        Clock.schedule_once(gen_then_continue, 0.1)

    def _load_state(self, data):
        self.puzzle = data['puzzle']
        self.solution = data['solution']
        self.current = data['current']
        self.notes = [[set(s) for s in row] for row in data.get('notes', [[[]] * 9] * 9)]
        self.errors = data.get('errors', 0)
        self.hints_used = data.get('hints_used', 0)
        self.error_cells = set(tuple(x) for x in data.get('error_cells', []))
        self.elapsed = data.get('elapsed', 0)
        self.start_time = time.time() - self.elapsed
        self.history = data.get('history', [])
        self._refresh_all()

    def save_state(self):
        if self.game_over or self.current is None:
            return
        if not self.paused:
            self.elapsed = int(time.time() - self.start_time)
        data = {
            'difficulty': self.difficulty,
            'puzzle': self.puzzle,
            'solution': self.solution,
            'current': self.current,
            'notes': [[list(s) for s in row] for row in self.notes],
            'errors': self.errors,
            'hints_used': self.hints_used,
            'error_cells': list(self.error_cells),
            'elapsed': self.elapsed,
            'history': self.history,
        }
        save_json(SAVE_FILE, data)

    def go_home(self):
        self.save_state()
        self.cleanup()
        self.app.show_home()

    def _cell_bg(self, r, c):
        sel = self.selected_cell
        val_here = self.current[r][c]
        active_val = None
        if self.selected_value is not None:
            active_val = self.selected_value
        elif sel and self.current[sel[0]][sel[1]] != 0:
            active_val = self.current[sel[0]][sel[1]]

        if sel and (r, c) == sel:
            return T.CELL_SELECTED
        if active_val:
            if val_here == active_val and val_here != 0:
                return T.CELL_SAME_NUM
            if val_here == 0 and active_val in self.notes[r][c]:
                return T.CELL_RELATED
        if sel:
            sr, sc = sel
            same_block = (sr // 3 == r // 3) and (sc // 3 == c // 3)
            if sr == r or sc == c or same_block:
                return T.CELL_RELATED
        return T.CELL_BG

    def on_cell_clicked(self, r, c):
        try:
            val_here = self.current[r][c]

            if val_here != 0:
                self.selected_cell = (r, c)
                self.selected_value = val_here
                self._refresh_all()
                return

            self.selected_cell = (r, c)
            if not self.hold_mode:
                self.selected_value = None
            elif self.hold_mode and self.hold_number is not None:
                if self.notes_mode:
                    self._toggle_note(r, c, self.hold_number)
                else:
                    self._place(r, c, self.hold_number)
                self.selected_value = self.hold_number
                
            self._refresh_all()
        except Exception as e:
            # S'il y a un bug, ça l'affiche au lieu de fermer l'appli !
            self.err_label.text = "Bug grille: " + str(e)[:15]
            self.err_label.color = T.DANGER

    

    def toggle_notes(self):
        if self.game_over or self.paused:
            return
        self.notes_mode = not self.notes_mode
        ic, tx = int(dp(22)), int(dp(11))
        
        if self.notes_mode:
            self.notes_btn.text = f'[font=fa-solid-900.ttf][size={ic}]\uf303[/size][/font]\n[size={tx}]Notes ON[/size]'
            self.notes_btn.text_color = T.PRIMARY
        else:
            self.notes_btn.text = f'[font=fa-solid-900.ttf][size={ic}]\uf303[/size][/font]\n[size={tx}]Notes OFF[/size]'
            self.notes_btn.text_color = T.TEXT_MUTED
          
    def _erase_cell(self, r, c):
        if self.puzzle[r][c] != 0:
            return
        if self.current[r][c] != 0:
            self._place(r, c, 0)
        elif self.notes[r][c]:
            self.history.append({
                'type': 'erase_notes', 'r': r, 'c': c,
                'notes_before': list(self.notes[r][c])
            })
            self.notes[r][c] = set()

    def _is_complete(self):
        return all(self.current[r][c] == self.solution[r][c]
                   for r in range(9) for c in range(9))

    def undo(self):
        if self.paused or self.game_over or not self.history:
            return
        last = self.history.pop()
        r, c = last['r'], last['c']
        if last['type'] == 'value':
            self.current[r][c] = last['prev']
            self.notes[r][c] = set(last.get('notes_before', []))
            if last['was_err']:
                self.error_cells.add((r, c))
            else:
                self.error_cells.discard((r, c))
            self.errors = last['errors']
        elif last['type'] == 'note':
            self.notes[r][c] = set(last['notes_before'])
        elif last['type'] == 'erase_notes':
            self.notes[r][c] = set(last['notes_before'])
        self._refresh_all()

    def erase(self):
        if self.paused or self.game_over or self.selected_cell is None:
            return
        r, c = self.selected_cell
        if self.puzzle[r][c] != 0:
            return
        self._erase_cell(r, c)
        self.selected_value = None
        self._refresh_all()

    def toggle_notes(self):
        if self.game_over or self.paused:
            return
        self.notes_mode = not self.notes_mode
        if self.notes_mode:
            self.notes_btn.text = '[size=20]N[/size]\n[size=9]Notes ON[/size]'
            self.notes_btn.bg_color = T.PRIMARY
            self.notes_btn.text_color = T.TEXT_LIGHT
            self.notes_btn.border_color = T.PRIMARY
        else:
            self.notes_btn.text = '[size=20]N[/size]\n[size=9]Notes OFF[/size]'
            self.notes_btn.bg_color = T.CARD
            self.notes_btn.text_color = T.TEXT_DARK
            self.notes_btn.border_color = T.GRID_LINE

    def toggle_pause(self):
        if self.game_over:
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.text = '>'
        else:
            self.pause_btn.text = '||'
            self.start_time = time.time() - self.elapsed
        self.grid._redraw()

    def use_hint(self):
        if self.paused or self.game_over:
            return

        # Vérifier qu'on a encore des astuces
        remaining = self.max_hints - self.hints_used
        if remaining <= 0:
            HintDialog(
                title='Plus d\'astuces',
                explanation='Vous avez deja utilise vos {} astuces pour cette partie.\n\nA vous de jouer !'.format(self.max_hints),
                on_close=None
            ).open()
            return

        # Trouver l'astuce intelligente
        hint = HintFinder.find_hint(self.puzzle, self.current, self.solution)
        if not hint:
            return

        r, c, num, explanation = hint

        # Afficher d'abord l'explication
        def reveal():
            # Placer la valeur après explication
            self.history.append({
                'type': 'value', 'r': r, 'c': c,
                'prev': self.current[r][c],
                'was_err': (r, c) in self.error_cells,
                'errors': self.errors,
                'notes_before': list(self.notes[r][c])
            })
            self.current[r][c] = num
            self.notes[r][c] = set()
            self.error_cells.discard((r, c))
            self.selected_cell = (r, c)
            self.selected_value = num
            self.hints_used += 1
            self._refresh_all()
            if self._is_complete():
                self._game_won()

        new_remaining = remaining - 1
        HintDialog(
            title='Astuce ({} restante{})'.format(
                new_remaining, 's' if new_remaining > 1 else ''),
            explanation=explanation,
            on_close=reveal
        ).open()

    def on_number_tap(self, num):
        try:
            if self.paused or self.game_over:
                return
            if self.hold_mode:
                if self.hold_number == num:
                    self._cancel_hold_mode()
                else:
                    self.hold_number = num
                    self.selected_value = num
                    mode_txt = 'notes' if self.notes_mode else 'placement'
                    self.hold_label.text = f'Mode rapide ({mode_txt}): {num}'
                    self._refresh_all()
            else:
                if self.selected_cell is not None:
                    r, c = self.selected_cell
                    if self.puzzle[r][c] == 0:
                        if self.notes_mode:
                            self._toggle_note(r, c, num)
                        else:
                            self._place(r, c, num)
                        self.selected_value = num
                        self._refresh_all()
                        return
                self.selected_value = num
                self._refresh_all()
        except Exception as e:
            # S'il y a un bug, ça l'affiche au lieu de fermer l'appli !
            self.err_label.text = "Bug chiffre: " + str(e)[:15]
            self.err_label.color = T.DANGER

    def on_number_long(self, num):
        if self.paused or self.game_over:
            return
        self.hold_mode = True
        self.hold_number = num
        self.selected_value = num
        mode_txt = 'notes' if self.notes_mode else 'placement'
        self.hold_label.text = 'Mode rapide ({}): {}'.format(mode_txt, num)
        self._refresh_all()

    def _cancel_hold_mode(self):
        self.hold_mode = False
        self.hold_number = None
        self.hold_label.text = ''
        self._refresh_all()

    def _refresh_all(self):
        self.err_label.text = f'Erreur: {self.errors}/{self.max_errors}'
        self.err_label.color = T.DANGER if self.errors >= 2 else T.TEXT_MUTED

        remaining = self.max_hints - self.hints_used
        ic, tx = int(dp(22)), int(dp(11))
        
        self.hint_btn.text = f'[font=fa-solid-900.ttf][size={ic}]\uf0eb[/size][/font]\n[size={tx}]Astuce {remaining}/{self.max_hints}[/size]'
        self.hint_btn.text_color = T.TEXT_GREY if remaining <= 0 else T.TEXT_MUTED

        counts = {n: 9 for n in range(1, 10)}
        if self.current:
            for r in range(9):
                for c in range(9):
                    v = self.current[r][c]
                    if v != 0 and (r, c) not in self.error_cells:
                        counts[v] = max(0, counts[v] - 1)
                        
        for n, btn in self.num_buttons.items():
            btn.count_left = counts[n]
            btn.is_active = self.hold_mode and self.hold_number == n
        self.grid._redraw()

    def _update_timer(self, dt):
        if self.game_over:
            return
        if not self.paused:
            self.elapsed = int(time.time() - self.start_time)
        m, s = self.elapsed // 60, self.elapsed % 60
        self.timer_label.text = '{:02d}:{:02d}'.format(m, s)

    def _game_won(self):
        self.game_over = True
        self.app.record_game(self.difficulty, True, self.errors, self.elapsed)
        try:
            os.remove(SAVE_FILE)
        except Exception:
            pass
        self.app.saved_game = None
        m, s = self.elapsed // 60, self.elapsed % 60
        EndDialog(
            title='Bravo !',
            subtitle='Resolu en {:02d}:{:02d}'.format(m, s),
            detail='{} - {}/3 erreur(s)'.format(self.difficulty, self.errors),
            color=T.SUCCESS,
            on_close=self.app.show_home
        ).open()

    def _game_lost(self):
        self.game_over = True
        self.app.record_game(self.difficulty, False, self.errors, self.elapsed)
        try:
            os.remove(SAVE_FILE)
        except Exception:
            pass
        self.app.saved_game = None
        EndDialog(
            title='Partie perdue',
            subtitle='3 erreurs atteintes',
            detail="Revenez a l'accueil pour rejouer",
            color=T.DANGER,
            on_close=self.app.show_home
        ).open()


# ============================================================
#  POPUPS
# ============================================================
class LoadingPopup(ModalView):
    def __init__(self, text, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(240), dp(100)),
                         background='',background_color=T.CARD, **kwargs)
        self.add_widget(Label(text=text, color=T.TEXT_DARK,
                              font_size=dp(13)))


class EndDialog(ModalView):
    def __init__(self, title, subtitle, detail, color, on_close, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(280), dp(260)),
                         background='', background_color=T.CARD, **kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(8))
        layout.add_widget(Label(text='[b]{}[/b]'.format(title), markup=True,
                                font_size=dp(22), color=color,
                                size_hint_y=None, height=dp(40)))
        layout.add_widget(Label(text=subtitle, font_size=dp(14),
                                color=T.TEXT_DARK,
                                size_hint_y=None, height=dp(26)))
        layout.add_widget(Label(text=detail, font_size=dp(11),
                                color=T.TEXT_MUTED,
                                size_hint_y=None, height=dp(20)))
        layout.add_widget(Widget())
        btn = FlatButton(text="Retour a l'accueil",
                         font_size=dp(13), bold=True,
                         bg_color=T.PRIMARY, border_color=T.PRIMARY,
                         text_color=T.TEXT_LIGHT,
                         size_hint_y=None, height=dp(44))
        btn.bind(on_release=lambda b: (self.dismiss(), on_close()))
        layout.add_widget(btn)
        self.add_widget(layout)


class HintDialog(ModalView):
    def __init__(self, title, explanation, on_close, **kwargs):
        super().__init__(size_hint=(0.88, None), height=dp(380),
                         background='',background_color=T.CARD, **kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))

        # Icone + titre
        header = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        icon = Label(text='[b]?[/b]', markup=True,
                     font_size=dp(32), color=T.WARNING,
                     size_hint_x=None, width=dp(40))
        header.add_widget(icon)
        title_lbl = Label(text='[b]{}[/b]'.format(title), markup=True,
                          font_size=dp(16), color=T.TEXT_DARK,
                          halign='left', valign='middle')
        title_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        header.add_widget(title_lbl)
        layout.add_widget(header)

        # Texte d'explication
        scroll = ScrollView()
        expl = Label(text=explanation, font_size=dp(12),
                     color=T.TEXT_DARK,
                     halign='left', valign='top',
                     size_hint_y=None)
        expl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
        expl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        scroll.add_widget(expl)
        layout.add_widget(scroll)

        # Boutons
        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        if on_close is not None:
            cancel_btn = FlatButton(text='Annuler', font_size=dp(12), bold=True,
                                    bg_color=T.CARD, border_color=T.GRID_LINE,
                                    text_color=T.TEXT_DARK)
            cancel_btn.bind(on_release=lambda b: self.dismiss())
            btns.add_widget(cancel_btn)

            ok_btn = FlatButton(text='Reveler', font_size=dp(12), bold=True,
                                bg_color=T.PRIMARY, border_color=T.PRIMARY,
                                text_color=T.TEXT_LIGHT)
            ok_btn.bind(on_release=lambda b: (self.dismiss(), on_close()))
            btns.add_widget(ok_btn)
        else:
            ok_btn = FlatButton(text='OK', font_size=dp(12), bold=True,
                                bg_color=T.PRIMARY, border_color=T.PRIMARY,
                                text_color=T.TEXT_LIGHT)
            ok_btn.bind(on_release=lambda b: self.dismiss())
            btns.add_widget(ok_btn)
        layout.add_widget(btns)

        self.add_widget(layout)


# ============================================================
#  ÉCRAN ACCUEIL
# ============================================================
class HomeScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        with self.canvas.before:
            Color(*T.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self._build()

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(54),
                        padding=[dp(16), dp(10), dp(16), 0], spacing=dp(8))
        help_btn = FlatButton(text='?', font_size=dp(20), bold=True,
                              bg_color=T.CARD, border_color=T.GRID_LINE,
                              text_color=T.TEXT_DARK,
                              size_hint_x=None, width=dp(50))
        help_btn.bind(on_release=lambda b: self.app.show_help())
        top.add_widget(help_btn)
        top.add_widget(Widget())
        stats_btn = FlatButton(text='*', font_size=dp(20), bold=True,
                               bg_color=T.CARD, border_color=T.GRID_LINE,
                               text_color=T.WARNING,
                               size_hint_x=None, width=dp(50))
        stats_btn.bind(on_release=lambda b: self.app.show_stats())
        top.add_widget(stats_btn)
        self.add_widget(top)

        title_box = AnchorLayout(size_hint_y=None, height=dp(120),
                                 anchor_x='center', anchor_y='center')
        title_box.add_widget(Label(text='[b]SUDOKU[/b]', markup=True,
                                   font_size=dp(46), color=T.TEXT_GREY))
        self.add_widget(title_box)

        body = BoxLayout(orientation='vertical', padding=[dp(20), 0],
                         spacing=dp(10))

        if self.app.saved_game:
            body.add_widget(self._build_resume_card())

        lbl = Label(text='Choisir un niveau', font_size=dp(12),
                    color=T.TEXT_MUTED, bold=True,
                    size_hint_y=None, height=dp(22), halign='left')
        lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        body.add_widget(lbl)

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for diff in ('Facile', 'Moyen', 'Difficile', 'Expert'):
            grid.add_widget(self._build_diff_tile(diff))
        body.add_widget(grid)
        body.add_widget(Widget())
        self.add_widget(body)

        bottom_area = BoxLayout(size_hint_y=None, height=dp(90),
                                padding=[dp(20), dp(8), dp(20), dp(16)])
        new_btn = FlatButton(text='Nouvelle Partie',
                             font_size=dp(16), bold=True,
                             bg_color=T.PRIMARY, border_color=T.PRIMARY,
                             text_color=T.TEXT_LIGHT,
                             radius=dp(28))
        new_btn.bind(on_release=lambda b: self.app.show_difficulty_select())
        bottom_area.add_widget(new_btn)
        self.add_widget(bottom_area)

        self.add_widget(self.app.build_bottom_nav('home'))

    def _build_resume_card(self):
        sg = self.app.saved_game
        diff = sg.get('difficulty', 'Moyen')
        elapsed = sg.get('elapsed', 0)
        errors = sg.get('errors', 0)
        m, s = elapsed // 60, elapsed % 60

        card = FlatButton(
            text=f'[b]Reprendre la partie[/b]\n[size={int(dp(11))}]{diff} - {m:02d}:{s:02d} - {errors}/3[/size]',
            markup=True, font_size=dp(14),
            halign='center', valign='middle',
            bg_color=T.SUCCESS, border_color=T.SUCCESS,
            text_color=T.TEXT_LIGHT,
            size_hint_y=None, height=dp(70))
        card.bind(on_release=lambda b: self.app.resume_game())
        return card

    def _build_diff_tile(self, diff):
        color = T.DIFF_COLORS[diff]
        stats = self.app.stats[diff]
        best = stats.get('best_time')
        best_str = f'{best // 60:02d}:{best % 60:02d}' if best else '-'

        btn = FlatButton(
            text=f'[b]{diff}[/b]\n[size={int(dp(10))}]Record: {best_str}[/size]',
            font_size=dp(15), markup=True,
            halign='center', valign='middle',
            bg_color=T.CARD, border_color=color,
            text_color=color,
            size_hint_y=None, height=dp(80))
        btn.bind(on_release=lambda b, d=diff: self.app.start_new_game(d))
        return btn


# ============================================================
#  ÉCRAN DIFFICULTÉ
# ============================================================
class DifficultyScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        with self.canvas.before:
            Color(*T.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self._build()

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(54),
                        padding=[dp(16), dp(10), dp(16), 0])
        back = FlatButton(text='<', font_size=dp(20), bold=True,
                          bg_color=T.CARD, border_color=T.GRID_LINE,
                          text_color=T.TEXT_DARK,
                          size_hint_x=None, width=dp(50))
        back.bind(on_release=lambda b: self.app.show_home())
        top.add_widget(back)
        top.add_widget(Widget())
        self.add_widget(top)

        self.add_widget(Label(text='[b]Nouvelle partie[/b]', markup=True,
                              font_size=dp(22), color=T.TEXT_DARK,
                              size_hint_y=None, height=dp(40)))
        self.add_widget(Label(text='Choisissez la difficulte',
                              font_size=dp(11), color=T.TEXT_MUTED,
                              size_hint_y=None, height=dp(24)))

        body = BoxLayout(orientation='vertical',
                         padding=[dp(20), dp(8)], spacing=dp(10))
        descriptions = {
            'Facile': '~35 cases vides',
            'Moyen': '~45 cases vides',
            'Difficile': '~52 cases vides',
            'Expert': '~58 cases vides',
        }
        for diff in ('Facile', 'Moyen', 'Difficile', 'Expert'):
            body.add_widget(self._diff_card(diff, descriptions[diff]))
        body.add_widget(Widget())
        self.add_widget(body)
        self.add_widget(self.app.build_bottom_nav('home'))

    def _diff_card(self, diff, desc):
        color = T.DIFF_COLORS[diff]
        stats = self.app.stats[diff]
        best = stats.get('best_time')
        best_str = 'Record: {:02d}:{:02d}'.format(best // 60, best % 60) if best else 'Pas de record'

        btn = FlatButton(
            text='[b]{}[/b]\n[size=10]{}\n{}[/size]'.format(diff, desc, best_str),
            font_size=dp(15), markup=True,
            halign='center', valign='middle',
            bg_color=T.CARD, border_color=color,
            text_color=color,
            size_hint_y=None, height=dp(90))
        btn.bind(on_release=lambda b, d=diff: self.app.start_new_game(d))
        return btn


# ============================================================
#  ÉCRAN STATS
# ============================================================
class StatsScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        with self.canvas.before:
            Color(*T.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self._build()

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(54),
                        padding=[dp(16), dp(10), dp(16), 0])
        back = FlatButton(text='<', font_size=dp(20), bold=True,
                          bg_color=T.CARD, border_color=T.GRID_LINE,
                          text_color=T.TEXT_DARK,
                          size_hint_x=None, width=dp(50))
        back.bind(on_release=lambda b: self.app.show_home())
        top.add_widget(back)
        top.add_widget(Widget())
        self.add_widget(top)

        self.add_widget(Label(text='[b]Statistiques[/b]', markup=True,
                              font_size=dp(22), color=T.TEXT_DARK,
                              size_hint_y=None, height=dp(40)))

        tabs = BoxLayout(size_hint_y=None, height=dp(40),
                         padding=[dp(20), 0], spacing=dp(4))
        self.tab_buttons = {}
        for diff in ('Facile', 'Moyen', 'Difficile', 'Expert'):
            btn = FlatButton(text=diff, font_size=dp(10), bold=True,
                             bg_color=T.CARD, border_color=T.GRID_LINE,
                             text_color=T.TEXT_DARK)
            btn.bind(on_release=lambda b, d=diff: self._show_tab(d))
            tabs.add_widget(btn)
            self.tab_buttons[diff] = btn
        self.add_widget(tabs)

        self.content = BoxLayout(orientation='vertical',
                                 padding=[dp(20), dp(12)],
                                 spacing=dp(8))
        self.add_widget(self.content)

        self._show_tab('Facile')
        self.add_widget(self.app.build_bottom_nav('stats'))

    def _show_tab(self, diff):
        for d, btn in self.tab_buttons.items():
            if d == diff:
                btn.bg_color = T.DIFF_COLORS[d]
                btn.border_color = T.DIFF_COLORS[d]
                btn.text_color = T.TEXT_LIGHT
            else:
                btn.bg_color = T.CARD
                btn.border_color = T.GRID_LINE
                btn.text_color = T.TEXT_DARK

        self.content.clear_widgets()
        s = self.app.stats[diff]
        played = s['played']
        won = s['won']
        won_ne = s['won_no_err']
        total = s['total_time']
        best = s['best_time']
        win_rate = (won / played * 100) if played > 0 else 0
        avg = (total / won) if won > 0 else 0
        color = T.DIFF_COLORS[diff]

        hdr = Card(bg_color=color, border_color=color,
                   size_hint_y=None, height=dp(44))
        hdr.add_widget(Label(text='[b]Niveau {}[/b]'.format(diff), markup=True,
                             color=T.TEXT_LIGHT, font_size=dp(14)))
        self.content.add_widget(hdr)

        def fmt_time(t):
            if t:
                return '{:02d}:{:02d}'.format(int(t) // 60, int(t) % 60)
            return '-'

        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        grid.add_widget(self._stat_card('Parties', str(played)))
        grid.add_widget(self._stat_card('Gagnees', str(won),
                                        '{:.0f}% reussite'.format(win_rate) if played else ''))
        grid.add_widget(self._stat_card('Sans erreur', str(won_ne),
                                        '{:.0f}% des gains'.format(won_ne / won * 100) if won else ''))
        grid.add_widget(self._stat_card('Temps moyen', fmt_time(avg)))
        self.content.add_widget(grid)

        best_card = self._stat_card('Meilleur temps', fmt_time(best))
        self.content.add_widget(best_card)
        self.content.add_widget(Widget())

    def _stat_card(self, label, value, sub=''):
        card = Card(bg_color=T.CARD, border_color=T.GRID_LINE,
                    size_hint_y=None, height=dp(90), padding=dp(8))
        inner = BoxLayout(orientation='vertical')
        inner.add_widget(Label(text='[b]{}[/b]'.format(value), markup=True,
                               color=T.TEXT_DARK, font_size=dp(18),
                               size_hint_y=None, height=dp(30)))
        inner.add_widget(Label(text=label, color=T.TEXT_MUTED,
                               font_size=dp(10),
                               size_hint_y=None, height=dp(18)))
        if sub:
            inner.add_widget(Label(text=sub, color=T.TEXT_MUTED,
                                   font_size=dp(9), italic=True,
                                   size_hint_y=None, height=dp(14)))
        card.add_widget(inner)
        return card


# ============================================================
#  ÉCRAN AIDE
# ============================================================
class HelpScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        with self.canvas.before:
            Color(*T.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self._build()

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(54),
                        padding=[dp(16), dp(10), dp(16), 0])
        back = FlatButton(text='<', font_size=dp(20), bold=True,
                          bg_color=T.CARD, border_color=T.GRID_LINE,
                          text_color=T.TEXT_DARK,
                          size_hint_x=None, width=dp(50))
        back.bind(on_release=lambda b: self.app.show_home())
        top.add_widget(back)
        top.add_widget(Widget())
        self.add_widget(top)

        self.add_widget(Label(text='[b]Comment jouer[/b]', markup=True,
                              font_size=dp(22), color=T.TEXT_DARK,
                              size_hint_y=None, height=dp(40)))

        scroll = ScrollView()
        body = BoxLayout(orientation='vertical',
                         padding=[dp(20), dp(8)],
                         spacing=dp(8), size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))

        rules = [
            ('Objectif', 'Remplir la grille 9x9 pour que chaque ligne, colonne et carre 3x3 contienne tous les chiffres de 1 a 9.'),
            ('Saisir', 'Touchez une case puis un chiffre du pave.'),
            ('Notes', 'Activez Notes pour saisir des petits chiffres.'),
            ('Effacer', 'Efface la case selectionnee.'),
            ('Annuler', 'Reprend votre coup precedent.'),
            ('Mode rapide', 'Maintenez un chiffre pour le verrouiller.'),
            ('Astuces', '2 astuces maximum par partie. Chaque astuce explique la logique avant de reveler la valeur.'),
            ('Erreurs', '3 erreurs maximum. Chiffres incorrects en rouge.'),
        ]
        for title, text in rules:
            card = Card(bg_color=T.CARD, border_color=T.GRID_LINE,
                        size_hint_y=None, height=dp(80), padding=dp(10))
            txt = BoxLayout(orientation='vertical')
            t1 = Label(text='[b]{}[/b]'.format(title), markup=True,
                       font_size=dp(12), color=T.TEXT_DARK,
                       halign='left', valign='middle',
                       size_hint_y=None, height=dp(20))
            t1.bind(size=lambda i, v: setattr(i, 'text_size', v))
            txt.add_widget(t1)
            t2 = Label(text=text, font_size=dp(10), color=T.TEXT_MUTED,
                       halign='left', valign='top')
            t2.bind(size=lambda i, v: setattr(i, 'text_size', v))
            txt.add_widget(t2)
            card.add_widget(txt)
            body.add_widget(card)

        scroll.add_widget(body)
        self.add_widget(scroll)
        self.add_widget(self.app.build_bottom_nav('help'))


# ============================================================
#  APP PRINCIPALE
# ============================================================
class SudokuApp(App):
    title = 'Sudoku'

    def build(self):
        self.icon = 'icon.png'
        self.stats = load_json(STATS_FILE, default_stats())
        for d in ('Facile', 'Moyen', 'Difficile', 'Expert'):
            if d not in self.stats:
                self.stats[d] = default_stats()[d]
        self.saved_game = load_json(SAVE_FILE, None)
        self.game_screen = None

        self.root_layout = BoxLayout(orientation='vertical')
        self._show(HomeScreen(self))
        return self.root_layout

    def on_stop(self):
        if self.game_screen and not self.game_screen.game_over:
            self.game_screen.save_state()

    def on_pause(self):
        if self.game_screen and not self.game_screen.game_over:
            self.game_screen.save_state()
        return True

    def _show(self, widget):
        self.root_layout.clear_widgets()
        self.root_layout.add_widget(widget)

    def show_home(self):
        if self.game_screen and not self.game_screen.game_over:
            self.game_screen.save_state()
            self.saved_game = load_json(SAVE_FILE, None)
        if self.game_screen:
            self.game_screen.cleanup()
            self.game_screen = None
        self._show(HomeScreen(self))

    def show_difficulty_select(self):
        self._show(DifficultyScreen(self))

    def show_stats(self):
        self._show(StatsScreen(self))

    def show_help(self):
        self._show(HelpScreen(self))

    def start_new_game(self, difficulty):
        try:
            os.remove(SAVE_FILE)
        except Exception:
            pass
        self.saved_game = None
        self.game_screen = GameScreen(self, difficulty)
        self._show(self.game_screen)

    def resume_game(self):
        if not self.saved_game:
            return
        self.game_screen = GameScreen(self, self.saved_game['difficulty'],
                                      resume_data=self.saved_game)
        self._show(self.game_screen)

    def discard_save(self):
        try:
            os.remove(SAVE_FILE)
        except Exception:
            pass
        self.saved_game = None
        self.show_home()

    def record_game(self, difficulty, won, errors, elapsed):
        s = self.stats.setdefault(difficulty, default_stats()[difficulty])
        s['played'] = s.get('played', 0) + 1
        if won:
            s['won'] = s.get('won', 0) + 1
            if errors == 0:
                s['won_no_err'] = s.get('won_no_err', 0) + 1
            s['total_time'] = s.get('total_time', 0) + elapsed
            if s.get('best_time') is None or elapsed < s['best_time']:
                s['best_time'] = elapsed
        save_json(STATS_FILE, self.stats)

    def build_bottom_nav(self, active):
        nav = BoxLayout(size_hint_y=None, height=dp(58),
                        padding=0, spacing=0)
        with nav.canvas.before:
            Color(*T.CARD)
            nav._rect = Rectangle(pos=nav.pos, size=nav.size)
        nav.bind(pos=lambda i, v: setattr(nav._rect, 'pos', v),
                 size=lambda i, v: setattr(nav._rect, 'size', v))

        items = [
            ('home', 'Principal', self.show_home),
            ('help', 'Regles', self.show_help),
            ('stats', 'Stats', self.show_stats),
        ]
        for key, label, cmd in items:
            color = T.NAV_ACTIVE if key == active else T.NAV_INACTIVE
            btn = FlatButton(
                text=('[b]' + label + '[/b]') if key == active else label,
                markup=True, font_size=dp(12),
                bg_color=T.CARD, border_color=[0, 0, 0, 0],
                text_color=color, radius=0)
            btn.bind(on_release=lambda b, c=cmd: c())
            nav.add_widget(btn)
        return nav


if __name__ == '__main__':
    SudokuApp().run()
