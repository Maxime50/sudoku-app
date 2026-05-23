"""
Sudoku — Application mobile Kivy
Portée pour Android via Buildozer
- Page d'accueil, sélection difficulté, statistiques, règles
- 4 niveaux, 3 erreurs max, notes, annuler, gomme, pause, astuce
- Mode appui long sur un chiffre
- Surlignage des chiffres identiques
- Sauvegarde / reprise persistantes
"""

import json
import os
import random
import copy
import time

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import (NumericProperty, StringProperty,
                             BooleanProperty, ListProperty, ObjectProperty)
from kivy.utils import get_color_from_hex as hex_to_rgba
from kivy.metrics import dp


# Fenêtre par défaut pour test desktop (ratio téléphone)
Window.size = (420, 820)


# ============================================================
#  THEME
# ============================================================
class T:
    BG = hex_to_rgba('#F4F6FB')
    CARD = hex_to_rgba('#FFFFFF')
    GRID_BORDER = hex_to_rgba('#1E2A47')
    GRID_LINE = hex_to_rgba('#E1E6F0')
    CELL_BG = hex_to_rgba('#FFFFFF')
    CELL_RELATED = hex_to_rgba('#EDF1F9')
    CELL_SAME_NUM = hex_to_rgba('#C9D9F2')
    CELL_SELECTED = hex_to_rgba('#A8C3EA')
    TEXT_DARK = hex_to_rgba('#1E2A47')
    TEXT_USER = hex_to_rgba('#2D6CDF')
    TEXT_NOTE = hex_to_rgba('#6B7A99')
    TEXT_ERROR = hex_to_rgba('#E53E3E')
    TEXT_LIGHT = hex_to_rgba('#FFFFFF')
    TEXT_MUTED = hex_to_rgba('#8A93A6')
    TEXT_GREY = hex_to_rgba('#B4BCCC')
    PRIMARY = hex_to_rgba('#2D6CDF')
    DANGER = hex_to_rgba('#E53E3E')
    SUCCESS = hex_to_rgba('#2EB67D')
    WARNING = hex_to_rgba('#F2A516')
    NAV_INACTIVE = hex_to_rgba('#B4BCCC')
    NAV_ACTIVE = hex_to_rgba('#2D6CDF')
    DIFF_COLORS = {
        'Facile': hex_to_rgba('#2EB67D'),
        'Moyen': hex_to_rgba('#2D6CDF'),
        'Difficile': hex_to_rgba('#F2A516'),
        'Expert': hex_to_rgba('#E53E3E'),
    }


# ============================================================
#  PERSISTANCE
# ============================================================
def _storage_dir():
    """Renvoie un dossier persistant valide même sur Android."""
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
        solution = copy.deepcopy(g)
        target = {'Facile': 35, 'Moyen': 45, 'Difficile': 52, 'Expert': 58}[difficulty]
        cells = [(i, j) for i in range(9) for j in range(9)]
        random.shuffle(cells)
        removed = 0
        for (r, c) in cells:
            if removed >= target:
                break
            backup = g[r][c]
            g[r][c] = 0
            if self.count(copy.deepcopy(g)) != 1:
                g[r][c] = backup
            else:
                removed += 1
        return copy.deepcopy(g), solution


# ============================================================
#  WIDGETS DE BASE
# ============================================================
class TappableBox(BoxLayout):
    """BoxLayout cliquable avec callback et couleur de fond"""
    bg_color = ListProperty(T.CARD)
    border_color = ListProperty([0, 0, 0, 0])
    radius = NumericProperty(dp(12))
    on_press_cb = ObjectProperty(None, allownone=True)
    _press_time = NumericProperty(0)
    _long_press_event = ObjectProperty(None, allownone=True)
    long_press_cb = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_color_instr = Color(*self.bg_color)
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size,
                radius=[(self.radius, self.radius)] * 4)
            self._border_color_instr = Color(*self.border_color)
            self._border_line = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height,
                                   self.radius),
                width=1.2)
        self.bind(pos=self._update, size=self._update,
                  bg_color=self._update_colors,
                  border_color=self._update_colors,
                  radius=self._update)

    def _update(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._bg_rect.radius = [(self.radius, self.radius)] * 4
        self._border_line.rounded_rectangle = (
            self.x, self.y, self.width, self.height, self.radius)

    def _update_colors(self, *a):
        self._bg_color_instr.rgba = self.bg_color
        self._border_color_instr.rgba = self.border_color

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._press_time = time.time()
            if self.long_press_cb:
                self._long_press_event = Clock.schedule_once(
                    lambda dt: self._fire_long_press(), 0.5)
            return super().on_touch_down(touch) or True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            if self._long_press_event:
                self._long_press_event.cancel()
                self._long_press_event = None
            elapsed = time.time() - self._press_time
            if elapsed < 0.5 and self.on_press_cb:
                self.on_press_cb()
            return True
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None
        return super().on_touch_up(touch)

    def _fire_long_press(self):
        self._long_press_event = None
        if self.long_press_cb:
            self.long_press_cb()


class IconLabel(Label):
    """Label avec callback au clic"""
    on_press_cb = ObjectProperty(None, allownone=True)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.on_press_cb:
            self.on_press_cb()
            return True
        return super().on_touch_down(touch)


# ============================================================
#  GRILLE SUDOKU
# ============================================================
class SudokuGrid(Widget):
    selected_cell = ObjectProperty(None, allownone=True)
    selected_value = ObjectProperty(None, allownone=True)

    def __init__(self, game_screen, **kwargs):
        super().__init__(**kwargs)
        self.game = game_screen
        self.bind(pos=self._redraw, size=self._redraw)

    @property
    def cell_size(self):
        return min(self.width, self.height) / 9.0

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self.game.paused or self.game.game_over:
            return True
        cs = self.cell_size
        if cs <= 0:
            return True
        col = int((touch.x - self.x) // cs)
        row = 8 - int((touch.y - self.y) // cs)  # inversion Y (Kivy = bas-gauche)
        if 0 <= row < 9 and 0 <= col < 9:
            self.game.on_cell_clicked(row, col)
        return True

    def _redraw(self, *a):
        self.canvas.clear()
        if not self.game.puzzle:
            return
        with self.canvas:
            cs = self.cell_size
            x0 = self.x
            y0 = self.y
            grid_size = cs * 9

            # Mode pause
            if self.game.paused:
                Color(*hex_to_rgba('#E1E6F0'))
                Rectangle(pos=(x0, y0), size=(grid_size, grid_size))
                Color(*T.GRID_BORDER)
                Line(rectangle=(x0, y0, grid_size, grid_size), width=2)
                Label(
                    text='[size=80]⏸[/size]\n[size=30][b]Pause[/b][/size]',
                    markup=True, color=T.TEXT_DARK,
                    halign='center', valign='middle',
                    pos=(x0, y0), size=(grid_size, grid_size),
                    text_size=(grid_size, grid_size)
                )
                return

            # Backgrounds des cases
            for r in range(9):
                for c in range(9):
                    bg = self.game._cell_bg(r, c)
                    Color(*bg)
                    cx = x0 + c * cs
                    cy = y0 + (8 - r) * cs
                    Rectangle(pos=(cx, cy), size=(cs, cs))

            # Lignes
            for i in range(10):
                if i % 3 == 0:
                    Color(*T.GRID_BORDER)
                    width = 1.8
                else:
                    Color(*T.GRID_LINE)
                    width = 1.0
                Line(points=[x0, y0 + i * cs, x0 + grid_size, y0 + i * cs],
                     width=width)
                Line(points=[x0 + i * cs, y0, x0 + i * cs, y0 + grid_size],
                     width=width)

        # Chiffres / notes via labels (clear puis re-add)
        self.clear_widgets()
        cs = self.cell_size
        x0 = self.x
        y0 = self.y
        for r in range(9):
            for c in range(9):
                v = self.game.current[r][c]
                cx = x0 + c * cs
                cy = y0 + (8 - r) * cs
                if v != 0:
                    if (r, c) in self.game.error_cells:
                        col = T.TEXT_ERROR
                    elif self.game.puzzle[r][c] != 0:
                        col = T.TEXT_DARK
                    else:
                        col = T.TEXT_USER
                    lbl = Label(
                        text=f'[b]{v}[/b]',
                        markup=True, color=col,
                        font_size=cs * 0.55,
                        pos=(cx, cy), size=(cs, cs),
                        halign='center', valign='middle')
                    lbl.text_size = (cs, cs)
                    self.add_widget(lbl)
                elif self.game.notes[r][c]:
                    for n in self.game.notes[r][c]:
                        nr = (n - 1) // 3
                        nc = (n - 1) % 3
                        nx = cx + nc * cs / 3
                        ny = cy + (2 - nr) * cs / 3
                        active = self.game.selected_value == n
                        col = T.PRIMARY if active else T.TEXT_NOTE
                        weight_open = '[b]' if active else ''
                        weight_close = '[/b]' if active else ''
                        lbl = Label(
                            text=f'{weight_open}{n}{weight_close}',
                            markup=True, color=col,
                            font_size=cs * 0.22,
                            pos=(nx, ny), size=(cs / 3, cs / 3),
                            halign='center', valign='middle')
                        lbl.text_size = (cs / 3, cs / 3)
                        self.add_widget(lbl)


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

        self._build_ui()

        if resume_data:
            self._load_state(resume_data)
        else:
            Clock.schedule_once(lambda dt: self._generate_new(), 0.05)

        self._timer_event = Clock.schedule_interval(self._update_timer, 1.0)

        # Bindings clavier (desktop)
        Window.bind(on_key_down=self._on_key_down)

    def cleanup(self):
        try:
            self._timer_event.cancel()
        except Exception:
            pass
        Window.unbind(on_key_down=self._on_key_down)

    # ----- UI -----
    def _build_ui(self):
        with self.canvas.before:
            Color(*T.BG)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Top bar
        top = BoxLayout(size_hint_y=None, height=dp(56),
                        padding=[dp(14), dp(10), dp(14), 0], spacing=dp(8))

        back_box = TappableBox(size_hint_x=None, width=dp(56),
                               bg_color=T.CARD,
                               border_color=T.GRID_LINE,
                               on_press_cb=self.go_home)
        back_box.add_widget(Label(text='←', font_size=dp(22),
                                  color=T.TEXT_DARK, bold=True))
        top.add_widget(back_box)
        top.add_widget(Widget())  # spacer

        right_pill = TappableBox(size_hint_x=None, width=dp(140),
                                 bg_color=T.CARD,
                                 border_color=T.GRID_LINE,
                                 spacing=dp(0))
        for icon, cmd in [('🏠', self.go_home),
                          ('🏆', self.app.show_stats),
                          ('⚙', self.app.show_help)]:
            il = IconLabel(text=icon, font_size=dp(14),
                           color=T.TEXT_DARK, on_press_cb=cmd)
            right_pill.add_widget(il)
        top.add_widget(right_pill)

        self.add_widget(top)

        # Ligne d'infos
        info = BoxLayout(size_hint_y=None, height=dp(28),
                         padding=[dp(20), 0, dp(20), 0])
        self.diff_label = Label(text=self.difficulty,
                                font_size=dp(12),
                                color=T.TEXT_MUTED,
                                size_hint_x=0.3, halign='left',
                                valign='middle')
        self.diff_label.bind(size=self._fix_label)
        info.add_widget(self.diff_label)

        self.err_label = Label(text='Erreur: 0/3',
                               font_size=dp(12),
                               color=T.TEXT_MUTED,
                               size_hint_x=0.4, halign='center',
                               valign='middle')
        self.err_label.bind(size=self._fix_label)
        info.add_widget(self.err_label)

        right_info = BoxLayout(size_hint_x=0.3, spacing=dp(4))
        self.timer_label = Label(text='00:00', font_size=dp(12),
                                 color=T.TEXT_MUTED,
                                 halign='right', valign='middle')
        self.timer_label.bind(size=self._fix_label)
        right_info.add_widget(self.timer_label)

        self.pause_icon = IconLabel(text='⏸', font_size=dp(14),
                                    color=T.PRIMARY,
                                    size_hint_x=None, width=dp(24),
                                    on_press_cb=self.toggle_pause)
        right_info.add_widget(self.pause_icon)
        info.add_widget(right_info)

        self.add_widget(info)

        # Grille (carrée)
        self.grid_anchor = AnchorLayout(size_hint_y=None,
                                        anchor_x='center',
                                        anchor_y='center',
                                        padding=[dp(16), dp(8)])
        self.grid_anchor.height = Window.width  # approximatif
        Window.bind(size=self._resize_grid)
        self.grid = SudokuGrid(self,
                               size_hint=(None, None))
        self.grid_anchor.add_widget(self.grid)
        self.add_widget(self.grid_anchor)
        Clock.schedule_once(lambda dt: self._resize_grid(), 0.01)

        # Boutons d'action
        actions = BoxLayout(size_hint_y=None, height=dp(70),
                            padding=[dp(8), dp(6)], spacing=dp(4))
        self.undo_btn = self._make_action_btn('↶', 'Annuler', self.undo)
        self.erase_btn = self._make_action_btn('⌫', 'Effacer', self.erase)
        self.notes_btn = self._make_action_btn('✎', 'Notes',
                                               self.toggle_notes, badge='ÉTEINT')
        self.hint_btn = self._make_action_btn('💡', 'Astuce', self.use_hint)
        for w in (self.undo_btn, self.erase_btn,
                  self.notes_btn, self.hint_btn):
            actions.add_widget(w['widget'])
        self.add_widget(actions)

        # Pavé numérique
        nums = BoxLayout(size_hint_y=None, height=dp(56),
                         padding=[dp(8), 0], spacing=dp(2))
        self.num_buttons = {}
        for i in range(1, 10):
            wrap = NumberButton(num=i, game=self)
            nums.add_widget(wrap)
            self.num_buttons[i] = wrap
        self.add_widget(nums)

        # Info mode rapide
        self.hold_label = Label(text='', font_size=dp(9),
                                color=T.WARNING,
                                size_hint_y=None, height=dp(22),
                                italic=True)
        self.add_widget(self.hold_label)

    def _update_bg(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _fix_label(self, instance, value):
        instance.text_size = instance.size

    def _resize_grid(self, *a):
        size = min(Window.width - dp(32), Window.height - dp(360))
        size = max(size, dp(200))
        # Garde un multiple de 9 pour pixel-perfect
        cell = int(size / 9)
        size = cell * 9
        self.grid.size = (size, size)
        self.grid_anchor.height = size + dp(16)
        self.grid._redraw()

    # ----- Boutons d'action -----
    def _make_action_btn(self, icon, label, command, badge=None):
        wrap = BoxLayout(orientation='vertical')
        rel = RelativeLayout(size_hint_y=None, height=dp(32))
        ic = IconLabel(text=icon, font_size=dp(20),
                       color=T.TEXT_DARK, on_press_cb=command)
        rel.add_widget(ic)

        badge_widget = None
        if badge is not None:
            badge_widget = BadgeLabel(text=badge,
                                      pos_hint={'right': 1, 'top': 1.05},
                                      size_hint=(None, None),
                                      size=(dp(50), dp(16)))
            rel.add_widget(badge_widget)

        wrap.add_widget(rel)
        lb = IconLabel(text=label, font_size=dp(10),
                       color=T.TEXT_MUTED, on_press_cb=command,
                       size_hint_y=None, height=dp(20))
        wrap.add_widget(lb)
        return {'widget': wrap, 'icon': ic, 'label': lb, 'badge': badge_widget}

    def _set_button_active(self, btn, active):
        if active:
            btn['icon'].color = T.PRIMARY
            btn['label'].color = T.PRIMARY
            if btn['badge']:
                btn['badge'].set_state('ALLUMÉ', T.SUCCESS)
        else:
            btn['icon'].color = T.TEXT_DARK
            btn['label'].color = T.TEXT_MUTED
            if btn['badge']:
                btn['badge'].set_state('ÉTEINT', hex_to_rgba('#9AA5BD'))

    # ----- Etat -----
    def _generate_new(self):
        loading = LoadingPopup('Génération de la grille...')
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
            'error_cells': list(self.error_cells),
            'elapsed': self.elapsed,
            'history': self.history,
        }
        save_json(SAVE_FILE, data)

    def go_home(self):
        self.save_state()
        self.cleanup()
        self.app.show_home()

    # ----- Cellule -----
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
        if self.hold_mode and self.hold_number is not None:
            if self.puzzle[r][c] == 0:
                if self.notes_mode:
                    self._toggle_note(r, c, self.hold_number)
                else:
                    cur = self.current[r][c]
                    if cur == self.hold_number:
                        self._place(r, c, 0)
                    else:
                        self._place(r, c, self.hold_number)
            self.selected_cell = (r, c)
            self.selected_value = self.hold_number
            self._refresh_all()
            return

        self.selected_cell = (r, c)
        v = self.current[r][c]
        self.selected_value = v if v != 0 else None
        self.grid._redraw()

    def _toggle_note(self, r, c, n):
        if self.puzzle[r][c] != 0 or self.current[r][c] != 0:
            return
        self.history.append({
            'type': 'note', 'r': r, 'c': c, 'n': n,
            'notes_before': list(self.notes[r][c])
        })
        if n in self.notes[r][c]:
            self.notes[r][c].discard(n)
        else:
            self.notes[r][c].add(n)

    def _place(self, r, c, num):
        if self.puzzle[r][c] != 0:
            return
        prev = self.current[r][c]
        was_err = (r, c) in self.error_cells
        if num == prev and not was_err:
            return

        self.history.append({
            'type': 'value', 'r': r, 'c': c, 'prev': prev,
            'was_err': was_err, 'errors': self.errors,
            'notes_before': list(self.notes[r][c])
        })

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
        else:
            if num == self.solution[r][c]:
                self.error_cells.discard((r, c))
            else:
                if not was_err:
                    self.errors += 1
                self.error_cells.add((r, c))
                if self.errors >= self.max_errors:
                    self._refresh_all()
                    self._game_lost()
                    return

        self._refresh_all()
        if self._is_complete():
            self._game_won()

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

    # ----- Actions -----
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
        self._set_button_active(self.notes_btn, self.notes_mode)

    def toggle_pause(self):
        if self.game_over:
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_icon.text = '▶'
        else:
            self.pause_icon.text = '⏸'
            self.start_time = time.time() - self.elapsed
        self.grid._redraw()

    def use_hint(self):
        if self.paused or self.game_over:
            return
        target = None
        if self.selected_cell is not None:
            r, c = self.selected_cell
            if self.puzzle[r][c] == 0 and self.current[r][c] != self.solution[r][c]:
                target = (r, c)
        if target is None:
            for r in range(9):
                for c in range(9):
                    if self.puzzle[r][c] == 0 and self.current[r][c] != self.solution[r][c]:
                        target = (r, c)
                        break
                if target:
                    break
        if not target:
            return
        r, c = target
        correct = self.solution[r][c]
        self.history.append({
            'type': 'value', 'r': r, 'c': c,
            'prev': self.current[r][c],
            'was_err': (r, c) in self.error_cells,
            'errors': self.errors,
            'notes_before': list(self.notes[r][c])
        })
        self.current[r][c] = correct
        self.notes[r][c] = set()
        self.error_cells.discard((r, c))
        self.selected_cell = (r, c)
        self.selected_value = correct
        self._refresh_all()
        if self._is_complete():
            self._game_won()

    # ----- Pavé numérique -----
    def on_number_tap(self, num):
        if self.paused or self.game_over:
            return
        if self.hold_mode:
            if self.hold_number == num:
                self._cancel_hold_mode()
            else:
                self.hold_number = num
                self.selected_value = num
                mode_txt = 'notes' if self.notes_mode else 'placement'
                self.hold_label.text = f'Mode rapide ({mode_txt}) : {num}'
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

    def on_number_long(self, num):
        if self.paused or self.game_over:
            return
        self.hold_mode = True
        self.hold_number = num
        self.selected_value = num
        mode_txt = 'notes' if self.notes_mode else 'placement'
        self.hold_label.text = f'Mode rapide ({mode_txt}) : {num}'
        self._refresh_all()

    def _cancel_hold_mode(self):
        self.hold_mode = False
        self.hold_number = None
        self.hold_label.text = ''
        self._refresh_all()

    # ----- Clavier (desktop) -----
    def _on_key_down(self, window, key, scancode, codepoint, modifier):
        if self.paused or self.game_over:
            if key == 27:  # Escape
                self._cancel_hold_mode()
            return
        if codepoint and codepoint in '123456789':
            n = int(codepoint)
            if self.selected_cell is None:
                self.selected_value = n
                self.grid._redraw()
                return
            r, c = self.selected_cell
            if self.puzzle[r][c] == 0:
                if self.notes_mode:
                    self._toggle_note(r, c, n)
                else:
                    self._place(r, c, n)
                self.selected_value = n
                self._refresh_all()
        elif key in (8, 46, 48):  # Backspace, Delete, 0
            if self.selected_cell:
                r, c = self.selected_cell
                if self.puzzle[r][c] == 0:
                    self._erase_cell(r, c)
                    self.selected_value = None
                    self._refresh_all()
        elif key == 273:  # Up
            self._move(-1, 0)
        elif key == 274:  # Down
            self._move(1, 0)
        elif key == 275:  # Right
            self._move(0, 1)
        elif key == 276:  # Left
            self._move(0, -1)
        elif key == 27:   # Escape
            self._cancel_hold_mode()
        elif codepoint in ('n', 'N'):
            self.toggle_notes()
        elif codepoint in ('p', 'P', ' '):
            self.toggle_pause()

    def _move(self, dr, dc):
        if self.selected_cell is None:
            self.selected_cell = (0, 0)
        else:
            r, c = self.selected_cell
            self.selected_cell = (max(0, min(8, r + dr)),
                                  max(0, min(8, c + dc)))
        r, c = self.selected_cell
        v = self.current[r][c]
        self.selected_value = v if v != 0 else None
        self.grid._redraw()

    # ----- Refresh -----
    def _refresh_all(self):
        self.err_label.text = f'Erreur: {self.errors}/{self.max_errors}'
        if self.errors >= 2:
            self.err_label.color = T.DANGER
        else:
            self.err_label.color = T.TEXT_MUTED
        # Compteurs des chiffres
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
            btn._redraw()
        self.grid._redraw()

    def _update_timer(self, dt):
        if self.game_over:
            return
        if not self.paused:
            self.elapsed = int(time.time() - self.start_time)
        m, s = self.elapsed // 60, self.elapsed % 60
        self.timer_label.text = f'{m:02d}:{s:02d}'

    # ----- Fin de partie -----
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
            subtitle=f'Résolu en {m:02d}:{s:02d}',
            detail=f'{self.difficulty} · {self.errors}/3 erreur(s)',
            color=T.SUCCESS, icon='🏆',
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
            detail="Revenez à l'accueil pour rejouer",
            color=T.DANGER, icon='✕',
            on_close=self.app.show_home
        ).open()


# ============================================================
#  WIDGETS AUXILIAIRES
# ============================================================
class BadgeLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = dp(8)
        self.bold = True
        self.color = T.TEXT_LIGHT
        self._bg_color = hex_to_rgba('#9AA5BD')
        with self.canvas.before:
            self._cc = Color(*self._bg_color)
            self._rect = RoundedRectangle(
                pos=self.pos, size=self.size,
                radius=[(dp(6), dp(6))] * 4)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_state(self, text, bg):
        self.text = text
        self._bg_color = bg
        self._cc.rgba = bg


class NumberButton(Widget):
    num = NumericProperty(1)
    count_left = NumericProperty(9)
    is_active = BooleanProperty(False)

    def __init__(self, num, game, **kwargs):
        super().__init__(**kwargs)
        self.num = num
        self.game = game
        self._press_time = 0
        self._long_event = None
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.clear()
        self.clear_widgets()
        if self.is_active:
            fg = T.PRIMARY
        elif self.count_left <= 0:
            fg = T.TEXT_GREY
        else:
            fg = T.PRIMARY
        lbl = Label(text=f'[b]{self.num}[/b]', markup=True,
                    color=fg, font_size=self.height * 0.5,
                    pos=self.pos, size=self.size,
                    halign='center', valign='middle')
        lbl.text_size = self.size
        self.add_widget(lbl)
        if self.is_active:
            with self.canvas:
                Color(*T.PRIMARY)
                Line(points=[
                    self.x + self.width / 2 - dp(14),
                    self.y + dp(4),
                    self.x + self.width / 2 + dp(14),
                    self.y + dp(4)
                ], width=2)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        self._press_time = time.time()
        self._long_event = Clock.schedule_once(
            lambda dt: self._fire_long(), 0.5)
        return True

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            if self._long_event:
                self._long_event.cancel()
                self._long_event = None
            return False
        if self._long_event:
            self._long_event.cancel()
            self._long_event = None
        elapsed = time.time() - self._press_time
        if elapsed < 0.5:
            self.game.on_number_tap(self.num)
        return True

    def _fire_long(self):
        self._long_event = None
        self.game.on_number_long(self.num)


class LoadingPopup(ModalView):
    def __init__(self, text, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(240), dp(100)),
                         background_color=T.CARD, **kwargs)
        self.add_widget(Label(text=text, color=T.TEXT_DARK,
                              font_size=dp(13)))


class EndDialog(ModalView):
    def __init__(self, title, subtitle, detail, color, icon, on_close, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(280), dp(280)),
                         background_color=T.CARD, **kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(8))
        layout.add_widget(Label(text=icon, font_size=dp(40), color=color,
                                size_hint_y=None, height=dp(60)))
        layout.add_widget(Label(text=f'[b]{title}[/b]', markup=True,
                                font_size=dp(20), color=color,
                                size_hint_y=None, height=dp(28)))
        layout.add_widget(Label(text=subtitle, font_size=dp(12),
                                color=T.TEXT_DARK,
                                size_hint_y=None, height=dp(20)))
        layout.add_widget(Label(text=detail, font_size=dp(10),
                                color=T.TEXT_MUTED,
                                size_hint_y=None, height=dp(20)))
        btn_box = TappableBox(bg_color=T.PRIMARY,
                              size_hint_y=None, height=dp(44),
                              on_press_cb=lambda: (self.dismiss(), on_close()))
        btn_box.add_widget(Label(text="Retour à l'accueil",
                                 color=T.TEXT_LIGHT, bold=True,
                                 font_size=dp(12)))
        layout.add_widget(btn_box)
        self.add_widget(layout)


# ============================================================
#  ÉCRANS NON-JEU
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
        # Top bar
        top = BoxLayout(size_hint_y=None, height=dp(50),
                        padding=[dp(20), dp(14), dp(20), 0])
        gear = IconLabel(text='⚙', font_size=dp(22), color=T.TEXT_DARK,
                         on_press_cb=self.app.show_help,
                         size_hint_x=None, width=dp(32))
        top.add_widget(gear)
        top.add_widget(Widget())
        trophy = IconLabel(text='🏆', font_size=dp(20), color=T.TEXT_DARK,
                           on_press_cb=self.app.show_stats,
                           size_hint_x=None, width=dp(32))
        top.add_widget(trophy)
        self.add_widget(top)

        # Titre SUDOKU
        title_box = AnchorLayout(size_hint_y=None, height=dp(80),
                                 anchor_x='center', anchor_y='center')
        title_box.add_widget(Label(text='[b]SUDOKU[/b]', markup=True,
                                   font_size=dp(38), color=T.TEXT_GREY))
        self.add_widget(title_box)

        body = BoxLayout(orientation='vertical', padding=[dp(20), 0],
                         spacing=dp(8))

        # Carte reprendre si dispo
        if self.app.saved_game:
            body.add_widget(self._build_resume_card())

        # Panneau choix de niveau
        lbl = Label(text='Choisir un niveau', font_size=dp(11),
                    color=T.TEXT_MUTED, bold=True,
                    size_hint_y=None, height=dp(20), halign='left')
        lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        body.add_widget(lbl)

        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        diffs = [('Facile', '🌱'), ('Moyen', '⚡'),
                 ('Difficile', '🔥'), ('Expert', '💎')]
        for diff, icon in diffs:
            grid.add_widget(self._build_diff_tile(diff, icon))
        body.add_widget(grid)

        body.add_widget(Widget())  # spacer

        self.add_widget(body)

        # Bouton "Nouvelle Partie" en bas
        bottom_btn_area = AnchorLayout(size_hint_y=None, height=dp(80),
                                       padding=[dp(20), 0, dp(20), dp(10)])
        new_btn = TappableBox(bg_color=T.CARD,
                              border_color=T.PRIMARY,
                              radius=dp(30),
                              size_hint=(1, None), height=dp(56),
                              on_press_cb=self.app.show_difficulty_select)
        new_btn.add_widget(Label(text='[b]Nouvelle Partie[/b]',
                                 markup=True, font_size=dp(16),
                                 color=T.PRIMARY))
        bottom_btn_area.add_widget(new_btn)
        self.add_widget(bottom_btn_area)

        # Bottom nav
        self.add_widget(self.app.build_bottom_nav('home'))

    def _build_resume_card(self):
        sg = self.app.saved_game
        diff = sg.get('difficulty', 'Moyen')
        elapsed = sg.get('elapsed', 0)
        errors = sg.get('errors', 0)
        m, s = elapsed // 60, elapsed % 60
        subtitle = f'{diff} · {m:02d}:{s:02d} · {errors}/3'

        card = TappableBox(bg_color=T.SUCCESS,
                           size_hint_y=None, height=dp(70),
                           padding=[dp(14), dp(10)],
                           on_press_cb=self.app.resume_game)

        play_icon = AnchorLayout(size_hint_x=None, width=dp(44),
                                 anchor_x='center', anchor_y='center')
        ic_bg = TappableBox(bg_color=T.TEXT_LIGHT,
                            size_hint=(None, None),
                            size=(dp(34), dp(34)), radius=dp(17))
        ic_bg.add_widget(Label(text='▶', color=T.SUCCESS, bold=True,
                               font_size=dp(16)))
        play_icon.add_widget(ic_bg)
        card.add_widget(play_icon)

        txt = BoxLayout(orientation='vertical', padding=[dp(10), 0])
        t1 = Label(text='[b]Reprendre la partie[/b]', markup=True,
                   color=T.TEXT_LIGHT, font_size=dp(13),
                   halign='left', valign='middle')
        t1.bind(size=lambda i, v: setattr(i, 'text_size', v))
        txt.add_widget(t1)
        t2 = Label(text=subtitle, color=hex_to_rgba('#D8F5E5'),
                   font_size=dp(10), halign='left', valign='middle')
        t2.bind(size=lambda i, v: setattr(i, 'text_size', v))
        txt.add_widget(t2)
        card.add_widget(txt)

        close = IconLabel(text='✕', color=hex_to_rgba('#D8F5E5'),
                          font_size=dp(13), bold=True,
                          size_hint_x=None, width=dp(28),
                          on_press_cb=self.app.discard_save)
        card.add_widget(close)
        return card

    def _build_diff_tile(self, diff, icon):
        color = T.DIFF_COLORS[diff]
        stats = self.app.stats[diff]
        best = stats.get('best_time')
        best_str = f"{best // 60:02d}:{best % 60:02d}" if best else "—"

        tile = TappableBox(bg_color=T.CARD,
                           border_color=T.GRID_LINE,
                           size_hint_y=None, height=dp(80),
                           padding=dp(12),
                           on_press_cb=lambda d=diff: self.app.start_new_game(d))
        inner = BoxLayout(orientation='vertical', spacing=dp(2))
        ic = Label(text=icon, color=color, font_size=dp(16),
                   size_hint_y=None, height=dp(20),
                   halign='left', valign='middle')
        ic.bind(size=lambda i, v: setattr(i, 'text_size', v))
        inner.add_widget(ic)

        t = Label(text=f'[b]{diff}[/b]', markup=True,
                  color=color, font_size=dp(13),
                  size_hint_y=None, height=dp(20),
                  halign='left', valign='middle')
        t.bind(size=lambda i, v: setattr(i, 'text_size', v))
        inner.add_widget(t)

        sub = Label(text=f'🏆 {best_str}', font_size=dp(9),
                    color=T.TEXT_MUTED,
                    size_hint_y=None, height=dp(16),
                    halign='left', valign='middle')
        sub.bind(size=lambda i, v: setattr(i, 'text_size', v))
        inner.add_widget(sub)
        tile.add_widget(inner)
        return tile


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
        top = BoxLayout(size_hint_y=None, height=dp(50),
                        padding=[dp(20), dp(14), dp(20), 0])
        back = IconLabel(text='←', font_size=dp(22), color=T.TEXT_DARK,
                         bold=True, on_press_cb=self.app.show_home,
                         size_hint_x=None, width=dp(40),
                         halign='left', valign='middle')
        back.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top.add_widget(back)
        top.add_widget(Widget())
        self.add_widget(top)

        title = Label(text='[b]Nouvelle partie[/b]', markup=True,
                      font_size=dp(22), color=T.TEXT_DARK,
                      size_hint_y=None, height=dp(40))
        self.add_widget(title)

        sub = Label(text='Choisissez la difficulté',
                    font_size=dp(11), color=T.TEXT_MUTED,
                    size_hint_y=None, height=dp(24))
        self.add_widget(sub)

        body = BoxLayout(orientation='vertical',
                         padding=[dp(20), dp(8)], spacing=dp(8))
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
        best_str = f"Record: {best // 60:02d}:{best % 60:02d}" if best else "Pas de record"

        card = TappableBox(bg_color=T.CARD,
                           border_color=T.GRID_LINE,
                           size_hint_y=None, height=dp(70),
                           padding=[0, 0],
                           on_press_cb=lambda d=diff: self.app.start_new_game(d))
        # Barre colorée à gauche
        bar = Widget(size_hint_x=None, width=dp(6))
        with bar.canvas:
            Color(*color)
            bar._rect = Rectangle(pos=bar.pos, size=bar.size)
        def update_bar(*a, b=bar):
            b._rect.pos = b.pos
            b._rect.size = b.size
        bar.bind(pos=update_bar, size=update_bar)
        card.add_widget(bar)

        inner = BoxLayout(orientation='vertical',
                          padding=[dp(14), dp(10)])
        l1 = BoxLayout(size_hint_y=None, height=dp(24))
        t1 = Label(text=f'[b]{diff}[/b]', markup=True,
                   color=color, font_size=dp(14),
                   halign='left', valign='middle')
        t1.bind(size=lambda i, v: setattr(i, 'text_size', v))
        l1.add_widget(t1)
        rec = Label(text=best_str, font_size=dp(9),
                    color=T.TEXT_MUTED,
                    halign='right', valign='middle')
        rec.bind(size=lambda i, v: setattr(i, 'text_size', v))
        l1.add_widget(rec)
        inner.add_widget(l1)

        t2 = Label(text=desc, font_size=dp(9),
                   color=T.TEXT_MUTED,
                   halign='left', valign='middle')
        t2.bind(size=lambda i, v: setattr(i, 'text_size', v))
        inner.add_widget(t2)
        card.add_widget(inner)
        return card


class StatsScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.current_tab = 'Facile'
        with self.canvas.before:
            Color(*T.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        self._build()

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _build(self):
        top = BoxLayout(size_hint_y=None, height=dp(50),
                        padding=[dp(20), dp(14), dp(20), 0])
        back = IconLabel(text='←', font_size=dp(22), color=T.TEXT_DARK,
                         bold=True, on_press_cb=self.app.show_home,
                         size_hint_x=None, width=dp(40),
                         halign='left', valign='middle')
        back.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top.add_widget(back)
        top.add_widget(Widget())
        self.add_widget(top)

        self.add_widget(Label(text='[b]Statistiques[/b]', markup=True,
                              font_size=dp(22), color=T.TEXT_DARK,
                              size_hint_y=None, height=dp(40)))

        # Tabs
        self.tabs_box = BoxLayout(size_hint_y=None, height=dp(36),
                                  padding=[dp(20), 0], spacing=dp(4))
        self.tab_buttons = {}
        for diff in ('Facile', 'Moyen', 'Difficile', 'Expert'):
            btn = TappableBox(bg_color=T.CARD,
                              size_hint_y=None, height=dp(32),
                              on_press_cb=lambda d=diff: self._show_tab(d))
            lbl = Label(text=diff, font_size=dp(9), color=T.TEXT_DARK,
                        bold=True)
            btn.add_widget(lbl)
            btn._lbl = lbl
            self.tabs_box.add_widget(btn)
            self.tab_buttons[diff] = btn
        self.add_widget(self.tabs_box)

        self.content = BoxLayout(orientation='vertical',
                                 padding=[dp(20), dp(12)],
                                 spacing=dp(6))
        self.add_widget(self.content)

        self._show_tab('Facile')
        self.add_widget(self.app.build_bottom_nav('stats'))

    def _show_tab(self, diff):
        self.current_tab = diff
        for d, btn in self.tab_buttons.items():
            if d == diff:
                btn.bg_color = T.DIFF_COLORS[d]
                btn._lbl.color = T.TEXT_LIGHT
            else:
                btn.bg_color = T.CARD
                btn._lbl.color = T.TEXT_DARK

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

        hdr = TappableBox(bg_color=color, size_hint_y=None, height=dp(40))
        hdr.add_widget(Label(text=f'[b]Niveau {diff}[/b]', markup=True,
                             color=T.TEXT_LIGHT, font_size=dp(14)))
        self.content.add_widget(hdr)

        fmt_time = lambda t: f'{int(t) // 60:02d}:{int(t) % 60:02d}' if t else '—'

        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        grid.add_widget(self._stat_card('Parties', str(played), '🎮', color))
        grid.add_widget(self._stat_card('Gagnées', str(won), '✓', color,
                                        f'{win_rate:.0f}% réussite' if played else ''))
        grid.add_widget(self._stat_card('Sans erreur', str(won_ne), '⭐', color,
                                        f'{(won_ne / won * 100):.0f}% des gains' if won else ''))
        grid.add_widget(self._stat_card('Temps moyen', fmt_time(avg), '⏱', color))
        self.content.add_widget(grid)

        best_card = self._stat_card('Meilleur temps', fmt_time(best), '🏆',
                                    color, big=True)
        best_card.size_hint_y = None
        best_card.height = dp(100)
        self.content.add_widget(best_card)
        self.content.add_widget(Widget())

    def _stat_card(self, label, value, icon, color, sub='', big=False):
        card = TappableBox(bg_color=T.CARD,
                           border_color=T.GRID_LINE,
                           size_hint_y=None, height=dp(100),
                           padding=dp(8))
        inner = BoxLayout(orientation='vertical')
        inner.add_widget(Label(text=icon, color=color, font_size=dp(16),
                               size_hint_y=None, height=dp(20)))
        inner.add_widget(Label(text=f'[b]{value}[/b]', markup=True,
                               color=T.TEXT_DARK, font_size=dp(18 if big else 16),
                               size_hint_y=None, height=dp(28)))
        inner.add_widget(Label(text=label, color=T.TEXT_MUTED,
                               font_size=dp(9),
                               size_hint_y=None, height=dp(16)))
        if sub:
            inner.add_widget(Label(text=sub, color=T.TEXT_MUTED,
                                   font_size=dp(8), italic=True,
                                   size_hint_y=None, height=dp(14)))
        card.add_widget(inner)
        return card


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
        top = BoxLayout(size_hint_y=None, height=dp(50),
                        padding=[dp(20), dp(14), dp(20), 0])
        back = IconLabel(text='←', font_size=dp(22), color=T.TEXT_DARK,
                         bold=True, on_press_cb=self.app.show_home,
                         size_hint_x=None, width=dp(40),
                         halign='left', valign='middle')
        back.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top.add_widget(back)
        top.add_widget(Widget())
        self.add_widget(top)

        self.add_widget(Label(text='[b]Comment jouer[/b]', markup=True,
                              font_size=dp(22), color=T.TEXT_DARK,
                              size_hint_y=None, height=dp(40)))

        scroll = ScrollView()
        body = BoxLayout(orientation='vertical',
                         padding=[dp(20), dp(8)],
                         spacing=dp(6), size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))

        rules = [
            ('🎯', 'Objectif',
             'Remplir la grille 9×9 pour que chaque ligne, colonne et carré 3×3 contienne tous les chiffres de 1 à 9.'),
            ('✏️', 'Saisir',
             'Touchez une case puis un chiffre du pavé.'),
            ('📝', 'Notes',
             'Activez Notes pour saisir des petits chiffres.'),
            ('⌫', 'Effacer',
             'Efface la case sélectionnée.'),
            ('↶', 'Annuler',
             'Reprend votre coup précédent.'),
            ('⚡', 'Mode rapide',
             'Maintenez un chiffre pour le verrouiller.'),
            ('⚠️', 'Erreurs',
             '3 erreurs maximum. Chiffres incorrects en rouge.'),
        ]
        for icon, title, text in rules:
            card = TappableBox(bg_color=T.CARD,
                               border_color=T.GRID_LINE,
                               size_hint_y=None, height=dp(80),
                               padding=dp(8))
            ic = Label(text=icon, font_size=dp(18), color=T.PRIMARY,
                       size_hint_x=None, width=dp(40))
            card.add_widget(ic)
            txt = BoxLayout(orientation='vertical')
            t1 = Label(text=f'[b]{title}[/b]', markup=True,
                       font_size=dp(11), color=T.TEXT_DARK,
                       halign='left', valign='middle',
                       size_hint_y=None, height=dp(20))
            t1.bind(size=lambda i, v: setattr(i, 'text_size', v))
            txt.add_widget(t1)
            t2 = Label(text=text, font_size=dp(9), color=T.TEXT_MUTED,
                       halign='left', valign='top')
            t2.bind(size=lambda i, v: setattr(i, 'text_size', v))
            txt.add_widget(t2)
            card.add_widget(txt)
            body.add_widget(card)

        scroll.add_widget(body)
        self.add_widget(scroll)
        self.add_widget(self.app.build_bottom_nav('help'))


# ============================================================
#  APP
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

    # ----- Navigation -----
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

    # ----- Bottom nav -----
    def build_bottom_nav(self, active):
        nav = TappableBox(bg_color=T.CARD,
                          border_color=T.GRID_LINE,
                          size_hint_y=None, height=dp(56),
                          padding=0)
        items = [
            ('home', '🏠', 'Principal', self.show_home),
            ('help', '❓', 'Règles', self.show_help),
            ('stats', '📊', 'Stats', self.show_stats),
        ]
        for key, icon, label, cmd in items:
            color = T.NAV_ACTIVE if key == active else T.NAV_INACTIVE
            item = TappableBox(bg_color=T.CARD, on_press_cb=cmd)
            inner = BoxLayout(orientation='vertical')
            inner.add_widget(Label(text=icon, color=color, font_size=dp(16),
                                   size_hint_y=None, height=dp(22)))
            inner.add_widget(Label(text=label, color=color, font_size=dp(9),
                                   bold=(key == active),
                                   size_hint_y=None, height=dp(16)))
            item.add_widget(inner)
            nav.add_widget(item)
        return nav


if __name__ == '__main__':
    SudokuApp().run()
