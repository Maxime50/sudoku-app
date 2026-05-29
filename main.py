"""
Sudoku — Application Android (Kivy)
- Grille pleine taille et centrée
- Interface modernisée et épurée
- Mise en évidence des chiffres identiques
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
                             ListProperty)
from kivy.utils import get_color_from_hex as hex_to_rgba, platform
from kivy.metrics import dp

if platform != 'android':
    Window.size = (420, 820)

# ============================================================
#  THEME (Optimisé pour ressembler à tes captures d'écran)
# ============================================================
class T:
    BG = hex_to_rgba('#F8F9FD') # Fond encore plus clair
    CARD = hex_to_rgba('#FFFFFF')
    GRID_BORDER = hex_to_rgba('#212A3E') # Bordure grille foncée
    GRID_LINE = hex_to_rgba('#D4D9E2') # Lignes internes discrètes
    CELL_BG = hex_to_rgba('#FFFFFF')
    CELL_RELATED = hex_to_rgba('#EBF0F8') # Ligne/colonne de la case (très clair)
    CELL_SAME_NUM = hex_to_rgba('#C5D4F0') # Chiffres identiques (bleu clair distinct)
    CELL_SELECTED = hex_to_rgba('#A4BEF3') # Case sélectionnée (bleu moyen)
    CELL_HINT = hex_to_rgba('#FFE89C')
    TEXT_DARK = hex_to_rgba('#212A3E')
    TEXT_USER = hex_to_rgba('#3A6DDF') # Chiffres de l'utilisateur en bleu franc
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
#  GÉNÉRATEUR & ANALYSEUR (Intacts)
# ============================================================
# [J'ai conservé toute la logique mathématique complexe de ton code original ici]
class SudokuGenerator:
    def is_valid(self, g, r, c, n):
        for x in range(9):
            if g[r][x] == n or g[x][c] == n: return False
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for i in range(3):
            for j in range(3):
                if g[br + i][bc + j] == n: return False
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
                        if self._full(g) or self.fill(g): return True
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
                        if t >= limit: return t
                return t
        return 1

    def generate(self, difficulty):
        g = [[0] * 9 for _ in range(9)]
        self.fill(g)
        solution = copy.deepcopy(g)
        target = {'Facile': 35, 'Moyen': 45, 'Difficile': 52, 'Expert': 58}[difficulty]
        cells = [(i, j) for i in range(9) for j in range(9)]
        random.shuffle(cells)
        removed = 0
        for (r, c) in cells:
            if removed >= target: break
            backup = g[r][c]
            g[r][c] = 0
            if self.count(copy.deepcopy(g)) != 1:
                g[r][c] = backup
            else:
                removed += 1
        return copy.deepcopy(g), solution

class HintFinder:
    @staticmethod
    def candidates(current, r, c):
        if current[r][c] != 0: return set()
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
        for r in range(9):
            for c in range(9):
                if current[r][c] == 0:
                    cands = HintFinder.candidates(current, r, c)
                    if len(cands) == 1:
                        num = cands.pop()
                        if num == solution[r][c]:
                            return (r, c, num, f"Cette case n'a qu'une seule valeur possible : {num}.")

        for r in range(9):
            for c in range(9):
                if current[r][c] == 0:
                    num = solution[r][c]
                    return (r, c, num, f"Essayez de placer {num} en ligne {r+1}, colonne {c+1}.")
        return None

# ============================================================
#  WIDGETS
# ============================================================
class FlatButton(Button):
    bg_color = ListProperty(T.CARD)
    border_color = ListProperty([0, 0, 0, 0])
    text_color = ListProperty(T.TEXT_DARK)
    radius = NumericProperty(dp(12)) # Bords un peu plus arrondis

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
    radius = NumericProperty(dp(12))

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
        self.canvas.clear()
        if not self.game.puzzle: return
        with self.canvas:
            cs = self.cell_size
            x0, y0 = self.x, self.y
            grid_size = cs * 9

            if self.game.paused:
                Color(*hex_to_rgba('#E1E6F0'))
                Rectangle(pos=(x0, y0), size=(grid_size, grid_size))
                return

            for r in range(9):
                for c in range(9):
                    bg = self.game._cell_bg(r, c)
                    Color(*bg)
                    Rectangle(pos=(x0 + c * cs, y0 + (8 - r) * cs), size=(cs, cs))

            for i in range(10):
                if i % 3 == 0:
                    Color(*T.GRID_BORDER)
                    width = 1.5
                else:
                    Color(*T.GRID_LINE)
                    width = 1.0
                Line(points=[x0, y0 + i * cs, x0 + grid_size, y0 + i * cs], width=width)
                Line(points=[x0 + i * cs, y0, x0 + i * cs, y0 + grid_size], width=width)

        self.clear_widgets()
        if self.game.paused: return
        
        for r in range(9):
            for c in range(9):
                v = self.game.current[r][c]
                cx, cy = x0 + c * cs, y0 + (8 - r) * cs
                if v != 0:
                    col = T.TEXT_ERROR if (r, c) in self.game.error_cells else (T.TEXT_DARK if self.game.puzzle[r][c] != 0 else T.TEXT_USER)
                    lbl = Label(text=f'[b]{v}[/b]', markup=True, color=col, font_size=cs * 0.55,
                                pos=(cx, cy), size=(cs, cs), halign='center', valign='middle')
                    lbl.text_size = (cs, cs)
                    self.add_widget(lbl)
                elif self.game.notes[r][c]:
                    for n in self.game.notes[r][c]:
                        nr, nc = (n - 1) // 3, (n - 1) % 3
                        nx, ny = cx + nc * cs / 3, cy + (2 - nr) * cs / 3
                        active = self.game.selected_value == n
                        col = T.PRIMARY if active else T.TEXT_NOTE
                        lbl = Label(text=f'[b]{n}[/b]' if active else str(n), markup=True, color=col,
                                    font_size=cs * 0.25, pos=(nx, ny), size=(cs / 3, cs / 3),
                                    halign='center', valign='middle')
                        lbl.text_size = (cs / 3, cs / 3)
                        self.add_widget(lbl)

class NumberButton(ButtonBehavior, Widget):
    num = NumericProperty(1)
    count_left = NumericProperty(9)
    is_active = BooleanProperty(False)

    def __init__(self, num, game, **kwargs):
        super().__init__(**kwargs)
        self.num = num
        self.game = game
        self.bind(pos=self._redraw, size=self._redraw, is_active=self._redraw, count_left=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.clear()
        self.clear_widgets()
        fg = T.PRIMARY if self.is_active or self.count_left > 0 else T.TEXT_GREY
        lbl = Label(text=f'[b]{self.num}[/b]', markup=True, color=fg, font_size=dp(32),
                    pos=self.pos, size=self.size, halign='center', valign='middle')
        lbl.text_size = self.size
        self.add_widget(lbl)

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
        self.errors, self.max_errors = 0, 3
        self.max_hints, self.hints_used = 2, 0
        self.selected_cell = None
        self.selected_value = None
        self.notes_mode = False
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
        if resume_data: self._load_state(resume_data)
        else: Clock.schedule_once(lambda dt: self._generate_new(), 0.05)
        self._timer_event = Clock.schedule_interval(self._update_timer, 1.0)

    def cleanup(self):
        try: self._timer_event.cancel()
        except: pass

    def _update_bg(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _build_ui(self):
        # Top bar
        top = BoxLayout(size_hint_y=None, height=dp(50), padding=[dp(15), dp(10), dp(15), 0])
        back_btn = FlatButton(text='<', font_size=dp(20), bold=True, size_hint_x=None, width=dp(40))
        back_btn.bind(on_release=lambda b: self.go_home())
        top.add_widget(back_btn)

        info = BoxLayout(orientation='vertical')
        self.diff_label = Label(text=self.difficulty, font_size=dp(12), color=T.TEXT_MUTED)
        info.add_widget(self.diff_label)
        
        row = BoxLayout(spacing=dp(15))
        self.err_label = Label(text='Erreur: 0/3', font_size=dp(12), color=T.TEXT_MUTED)
        self.timer_label = Label(text='00:00 ||', font_size=dp(12), color=T.TEXT_MUTED)
        row.add_widget(self.err_label)
        row.add_widget(self.timer_label)
        info.add_widget(row)
        top.add_widget(info)
        self.add_widget(top)

        # Grille
        self.grid_anchor = AnchorLayout(anchor_x='center', anchor_y='center', padding=[dp(15), dp(15)])
        self.grid = SudokuGrid(self, size_hint=(None, None))
        self.grid_anchor.add_widget(self.grid)
        self.add_widget(self.grid_anchor)
        Window.bind(size=self._resize_grid)
        Clock.schedule_once(lambda dt: self._resize_grid(), 0.1)

        # Actions avec Symboles Unicode plus jolis
        actions = BoxLayout(size_hint_y=None, height=dp(70), padding=[dp(10), dp(10)], spacing=dp(15))
        self.undo_btn = FlatButton(text='[size=24]↶[/size]\n[size=10]Annuler[/size]', markup=True, halign='center', valign='middle')
        self.undo_btn.bind(on_release=lambda b: self.undo())
        self.erase_btn = FlatButton(text='[size=20]✗[/size]\n[size=10]Effacer[/size]', markup=True, halign='center', valign='middle')
        self.erase_btn.bind(on_release=lambda b: self.erase())
        self.notes_btn = FlatButton(text='[size=20]✎[/size]\n[size=10]Notes[/size]', markup=True, halign='center', valign='middle')
        self.notes_btn.bind(on_release=lambda b: self.toggle_notes())
        self.hint_btn = FlatButton(text='[size=20]💡[/size]\n[size=10]Astuce[/size]', markup=True, halign='center', valign='middle')
        self.hint_btn.bind(on_release=lambda b: self.use_hint())
        
        for btn in [self.undo_btn, self.erase_btn, self.notes_btn, self.hint_btn]:
            actions.add_widget(btn)
        self.add_widget(actions)

        # Pavé numérique
        nums = BoxLayout(size_hint_y=None, height=dp(70), padding=[dp(10), dp(10)], spacing=dp(5))
        self.num_buttons = {}
        for i in range(1, 10):
            wrap = NumberButton(num=i, game=self)
            nums.add_widget(wrap)
            self.num_buttons[i] = wrap
        self.add_widget(nums)

    def _resize_grid(self, *a):
        ui_total = dp(50 + 70 + 70 + 30)
        size = min(Window.width - dp(30), Window.height - ui_total)
        size = max(size, dp(280))
        size = int(size / 9) * 9
        self.grid.size = (size, size)
        self.grid._redraw()

    def _generate_new(self):
        self.puzzle, self.solution = SudokuGenerator().generate(self.difficulty)
        self.current = copy.deepcopy(self.puzzle)
        self.notes = [[set() for _ in range(9)] for _ in range(9)]
        self.start_time = time.time()
        self._refresh_all()

    def _load_state(self, data):
        self.puzzle = data['puzzle']
        self.solution = data['solution']
        self.current = data['current']
        self.notes = [[set(s) for s in row] for row in data.get('notes', [[[]] * 9] * 9)]
        self.errors = data.get('errors', 0)
        self.error_cells = set(tuple(x) for x in data.get('error_cells', []))
        self.elapsed = data.get('elapsed', 0)
        self.start_time = time.time() - self.elapsed
        self.history = data.get('history', [])
        self._refresh_all()

    def save_state(self):
        if self.game_over or self.current is None: return
        self.elapsed = int(time.time() - self.start_time)
        data = {
            'difficulty': self.difficulty, 'puzzle': self.puzzle, 'solution': self.solution,
            'current': self.current, 'notes': [[list(s) for s in row] for row in self.notes],
            'errors': self.errors, 'error_cells': list(self.error_cells),
            'elapsed': self.elapsed, 'history': self.history,
        }
        save_json(SAVE_FILE, data)

    def go_home(self):
        self.save_state()
        self.cleanup()
        self.app.show_home()

    # C'est ici que s'opère la magie de la coloration des chiffres !
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
                return T.CELL_SAME_NUM # <-- Les cases avec le même chiffre sont mises en surbrillance
            if val_here == 0 and active_val in self.notes[r][c]:
                return T.CELL_RELATED
        if sel:
            sr, sc = sel
            if sr == r or sc == c or (sr // 3 == r // 3 and sc // 3 == c // 3):
                return T.CELL_RELATED
        return T.CELL_BG

    def on_cell_clicked(self, r, c):
        self.selected_cell = (r, c)
        v = self.current[r][c]
        self.selected_value = v if v != 0 else None
        self.grid._redraw()

    def _place(self, r, c, num):
        if self.puzzle[r][c] != 0: return
        prev = self.current[r][c]
        was_err = (r, c) in self.error_cells
        if num == prev and not was_err: return

        self.history.append({'type': 'value', 'r': r, 'c': c, 'prev': prev, 'was_err': was_err, 'errors': self.errors})
        self.current[r][c] = num
        
        if num != 0:
            self.notes[r][c] = set()
            for x in range(9):
                self.notes[r][x].discard(num)
                self.notes[x][c].discard(num)
            br, bc = 3 * (r // 3), 3 * (c // 3)
            for i in range(3):
                for j in range(3):
                    self.notes[br + i][bc + j].discard(num)

        if num == 0:
            self.error_cells.discard((r, c))
        elif num == self.solution[r][c]:
            self.error_cells.discard((r, c))
        else:
            if not was_err: self.errors += 1
            self.error_cells.add((r, c))
            if self.errors >= self.max_errors:
                self._refresh_all()
                return self._game_lost()

        self._refresh_all()
        if all(self.current[i][j] == self.solution[i][j] for i in range(9) for j in range(9)):
            self._game_won()

    def undo(self):
        if not self.history: return
        last = self.history.pop()
        r, c = last['r'], last['c']
        self.current[r][c] = last['prev']
        if last['was_err']: self.error_cells.add((r, c))
        else: self.error_cells.discard((r, c))
        self.errors = last['errors']
        self._refresh_all()

    def erase(self):
        if self.selected_cell:
            r, c = self.selected_cell
            self._place(r, c, 0)

    def toggle_notes(self):
        self.notes_mode = not self.notes_mode
        self.notes_btn.bg_color = T.PRIMARY if self.notes_mode else T.CARD
        self.notes_btn.text_color = T.TEXT_LIGHT if self.notes_mode else T.TEXT_DARK

    def use_hint(self):
        hint = HintFinder.find_hint(self.puzzle, self.current, self.solution)
        if hint:
            r, c, num, expl = hint
            self._place(r, c, num)
            self.selected_cell = (r, c)
            self.selected_value = num
            self._refresh_all()

    def on_number_tap(self, num):
        if self.selected_cell:
            r, c = self.selected_cell
            if self.puzzle[r][c] == 0:
                if self.notes_mode:
                    if num in self.notes[r][c]: self.notes[r][c].discard(num)
                    else: self.notes[r][c].add(num)
                else:
                    self._place(r, c, num)
        self.selected_value = num
        self._refresh_all()

    def _refresh_all(self):
        self.err_label.text = f'Erreur: {self.errors}/{self.max_errors}'
        counts = {n: 9 for n in range(1, 10)}
        if self.current:
            for r in range(9):
                for c in range(9):
                    v = self.current[r][c]
                    if v != 0 and (r, c) not in self.error_cells:
                        counts[v] = max(0, counts[v] - 1)
        for n, btn in self.num_buttons.items():
            btn.count_left = counts[n]
        self.grid._redraw()

    def _update_timer(self, dt):
        if self.game_over: return
        self.elapsed = int(time.time() - self.start_time)
        self.timer_label.text = f'{self.elapsed // 60:02d}:{self.elapsed % 60:02d} ||'

    def _game_won(self):
        self.game_over = True
        self.app.show_home()

    def _game_lost(self):
        self.game_over = True
        self.app.show_home()

# ============================================================
#  ÉCRAN ACCUEIL (Simplifié)
# ============================================================
class HomeScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        with self.canvas.before:
            Color(*T.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        
        # Titre
        title = AnchorLayout(size_hint_y=None, height=dp(150))
        title.add_widget(Label(text='[b]SUDOKU[/b]', markup=True, font_size=dp(40), color=T.PRIMARY))
        self.add_widget(title)

        body = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        if self.app.saved_game:
            res = FlatButton(text='[b]Reprendre la partie[/b]', markup=True, bg_color=T.PRIMARY, text_color=T.TEXT_LIGHT, size_hint_y=None, height=dp(60))
            res.bind(on_release=lambda b: self.app.resume_game())
            body.add_widget(res)

        grid = GridLayout(cols=2, spacing=dp(15), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for diff in ('Facile', 'Moyen', 'Difficile', 'Expert'):
            btn = FlatButton(text=f'[b]{diff}[/b]', markup=True, bg_color=T.CARD, text_color=T.DIFF_COLORS[diff], size_hint_y=None, height=dp(80))
            btn.bind(on_release=lambda b, d=diff: self.app.start_new_game(d))
            grid.add_widget(btn)
        body.add_widget(grid)
        body.add_widget(Widget())
        self.add_widget(body)

    def _upd(self, *a):
        self._bg.pos, self._bg.size = self.pos, self.size

class SudokuApp(App):
    def build(self):
        self.saved_game = load_json(SAVE_FILE, None)
        self.root_layout = BoxLayout(orientation='vertical')
        self._show(HomeScreen(self))
        return self.root_layout

    def _show(self, widget):
        self.root_layout.clear_widgets()
        self.root_layout.add_widget(widget)

    def show_home(self):
        self.saved_game = load_json(SAVE_FILE, None)
        self._show(HomeScreen(self))

    def start_new_game(self, difficulty):
        self._show(GameScreen(self, difficulty))

    def resume_game(self):
        self._show(GameScreen(self, self.saved_game['difficulty'], resume_data=self.saved_game))

if __name__ == '__main__':
    SudokuApp().run()
