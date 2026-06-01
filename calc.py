import sys
import os
from tkinter import *
from tkinter.font import Font

# Helper: resolve asset paths for both script mode and PyInstaller EXE mode
def resource_path(relative_path):
    
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)
import customtkinter as ctk

# Task-bar-icon
import ctypes 
myappid = 'mycompany.myproduct.subproduct.version'  # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# root window
root = ctk.CTk()
root.resizable(False, False)
root.configure(bg="black")
root.title("Calculator")
root.iconbitmap(resource_path("calc.ico"))

# Display frame - (Main number entry and history label)
display_frame = ctk.CTkFrame(root, width=320, height=80, corner_radius=10,
                              fg_color="#c2faff", border_width=2,border_color="#888")
display_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=10)
display_frame.grid_propagate(False)

# ── History area: canvas fills full top width, arrows overlaid on top ────
history_var = StringVar(value="")
HIST_W = 290  # canvas spans almost full frame width (frame is 310px wide)

# Canvas created FIRST so buttons (placed after) sit on top of it
_hist_canvas = Canvas(display_frame, width=HIST_W, height=20,
                       bg="#c2faff", bd=0, highlightthickness=0)
_hist_canvas.place(x=20, y=5, relwidth=1.0, width=-40)  # sits between the two arrow buttons
_hist_txt = _hist_canvas.create_text(HIST_W, 10, text="",
                                      anchor='e', font=('Arial', 14),
                                      fill="#000000")
_hist_x = HIST_W   # right-aligned: latest text is always visible by default

# ── Press-and-hold auto-scroll ──────────────────────────────────────────────
_hist_repeat_id  = None   # id for the fast-repeat after() job
_hist_initial_id = None   # id for the 400ms delay before repeat starts

def _repeat_hist_scroll(direction):
    """Called repeatedly while button is held (every 60ms)."""
    global _hist_repeat_id
    _scroll_hist(direction)
    _hist_repeat_id = root.after(60, lambda: _repeat_hist_scroll(direction))

def _begin_hist_scroll(direction):
    """ButtonPress: scroll once immediately, then start repeat after 400ms delay."""
    global _hist_initial_id
    _scroll_hist(direction)   # single step on first click
    _hist_initial_id = root.after(400, lambda: _repeat_hist_scroll(direction))

def _stop_hist_scroll(_event=None):
    """ButtonRelease: cancel both the initial delay and any ongoing repeat."""
    global _hist_repeat_id, _hist_initial_id
    if _hist_initial_id is not None:
        root.after_cancel(_hist_initial_id)
        _hist_initial_id = None
    if _hist_repeat_id is not None:
        root.after_cancel(_hist_repeat_id)
        _hist_repeat_id = None

# Left arrow (hidden initially — shown only when text overflows)
_btn_hl = Button(display_frame, text="‹", font=('Arial', 11, 'bold'),
                  bg="#c2faff", activebackground="#b0eff8",
                  relief='flat', bd=0, fg="#666", cursor='hand2')
_btn_hl.bind('<ButtonPress-1>',   lambda e: _begin_hist_scroll(+1))
_btn_hl.bind('<ButtonRelease-1>', _stop_hist_scroll)

# Right arrow (hidden initially)
_btn_hr = Button(display_frame, text="›", font=('Arial', 11, 'bold'),
                  bg="#c2faff", activebackground="#b0eff8",
                  relief='flat', bd=0, fg="#666", cursor='hand2')
_btn_hr.bind('<ButtonPress-1>',   lambda e: _begin_hist_scroll(-1))
_btn_hr.bind('<ButtonRelease-1>', _stop_hist_scroll)

def _canvas_right():
    """Actual rendered right edge of the canvas (fallback to HIST_W before layout)."""
    w = _hist_canvas.winfo_width()
    return w if w > 1 else HIST_W

def _update_arrow_visibility():
    """Show arrows only when text is wider than the visible canvas area."""
    bbox = _hist_canvas.bbox(_hist_txt)
    text_w = (bbox[2] - bbox[0]) if bbox else 0
    right  = _canvas_right()
    if text_w > right:       # text overflows → show arrows
        _btn_hl.place(x=4, y=5)
        _btn_hr.place(relx=1.0, x=-18, y=5)
    else:                    # text fits → hide arrows
        _btn_hl.place_forget()
        _btn_hr.place_forget()

def _scroll_hist(direction):
    """Scroll history: direction=+1 reveals earlier text, -1 goes back to latest."""
    global _hist_x
    STEP = 20
    right = _canvas_right()
    bbox = _hist_canvas.bbox(_hist_txt)
    if not bbox:
        return
    text_w = bbox[2] - bbox[0]
    if direction > 0:
        _hist_x = min(_hist_x + STEP, text_w)
    else:
        _hist_x = max(_hist_x - STEP, right)
    _hist_canvas.coords(_hist_txt, _hist_x, 10)

def _on_hist_change(*_):
    global _hist_x
    _hist_x = _canvas_right()
    _hist_canvas.itemconfig(_hist_txt, text=history_var.get())
    _hist_canvas.coords(_hist_txt, _hist_x, 10)
    root.after(10, _update_arrow_visibility)  # check after layout settles

history_var.trace_add('write', _on_hist_change)

# Main number entry 
e = ctk.CTkEntry(display_frame, width=300, height=42,
                  border_width=0, corner_radius=0,
                  text_color="black", font=('Sans', 28),
                  justify='right', fg_color="#c2faff")
e.place(relx=0.5, rely=1.0, anchor='s', y=-4)
e.insert(0, "0")  # show 0 when no operations are happening

# Prevent entry/frame from stealing keyboard focus
e.bind('<FocusIn>', lambda event: root.after(1, root.focus_set))
display_frame.bind('<FocusIn>', lambda event: root.after(1, root.focus_set))

new_number = False
f_num = 0.0
math = ""
running_expr = ""   # builds the full expression shown in history (e.g. "9 + 9 + 9 +")
last_operand = None  # saved second operand for repeat-= feature
last_math_op = ""   # saved operation for repeat-=
after_equal = False  # True right after = is pressed; used to detect repeat-=

# Function to avoid IEEE 754 float noise 
def smart_round(value):
    try:
        rounded = float(f"{value:.10g}") 
        return int(rounded) if rounded == int(rounded) else rounded
    except (ValueError, OverflowError):
        return value

# button-click-handler
def b_click(number):
    global new_number, after_equal
    after_equal = False  # typing a digit cancels repeat-= mode
    if new_number:
        e.delete(0, END)
        new_number = False
    current = e.get()
    # Replace a lone "0" with the new digit
    if current == "0" and str(number) != ".":
        e.delete(0, END)
        e.insert(0, str(number))
    else:
        e.delete(0, END)
        e.insert(0, str(current) + str(number))
# clear button
def button_clear():
    global f_num, math, new_number, running_expr, last_operand, last_math_op, after_equal
    e.delete(0, END)
    e.insert(0, "0")  # restore default 0 display
    history_var.set("")
    f_num = 0.0
    math = ""
    new_number = False
    running_expr = ""
    last_operand = None
    last_math_op = ""
    after_equal = False

# dictionary of operations symbols for history label
op_symbols = {
    "addition": "+", "subtraction": "-", "multiplication": "x",
    "division": "÷", "power": "^", "modulo": "%", "square_root": "√"
}

# function to clean trailing zeros from history label
def _clean_num_str(s):
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s if s else '0'

# function to get and clean the number
def _get_and_clean():
    val = e.get()
    if not val:
        return val
    clean = _clean_num_str(val)
    if clean != val:
        e.delete(0, END)
        e.insert(0, clean)
    return clean

# function to compute the result
def _chain_compute():
    global f_num, new_number
    if math == "" or new_number:
        return  
    second = e.get()
    if not second:
        return
    try:
        result = None
        if math == "addition":
            result = f_num + float(second)
        elif math == "subtraction":
            result = f_num - float(second)
        elif math == "multiplication":
            result = f_num * float(second)
        elif math == "division":
            if float(second) == 0: return
            result = f_num / float(second)
        elif math == "power":
            result = f_num ** float(second)
        elif math == "modulo":
            if int(float(second)) == 0: return
            result = int(f_num) % int(float(second))
        elif math == "square_root":
            result = f_num ** 0.5
        if result is not None:
            result = smart_round(result)
            f_num = result          # carry result forward
            e.delete(0, END)
            e.insert(0, result)
            new_number = True       # operator functions will read the result fresh
    except (ValueError, ZeroDivisionError, OverflowError):
        pass

   
# function to display result
def button_equal():
    global new_number, running_expr, f_num, last_operand, last_math_op, after_equal

    if after_equal and last_operand is not None:
        # ── Repeat-= mode: reapply last op with last operand ──
        use_operand = last_operand
        use_math    = last_math_op
        f_before    = f_num          # current result becomes the new first operand
    else:
        # ── Normal = : read second number from display ──
        raw = e.get()
        if not raw: return
        try:
            use_operand = float(raw)
        except ValueError:
            return
        use_math = math
        f_before = f_num

    e.delete(0, END)
    result = None
    try:
        if use_math == "addition":
            result = f_before + use_operand
        elif use_math == "subtraction":
            result = f_before - use_operand
        elif use_math == "multiplication":
            result = f_before * use_operand
        elif use_math == "division":
            if use_operand == 0:
                e.insert(0, "Div/0 Error")
                history_var.set("")
                running_expr = ""
                after_equal = False
                new_number = True
                return
            result = f_before / use_operand
        elif use_math == "power":
            result = f_before ** use_operand
        elif use_math == "modulo":
            if int(use_operand) == 0:
                e.insert(0, "Div/0 Error")
                history_var.set("")
                running_expr = ""
                after_equal = False
                new_number = True
                return
            result = int(f_before) % int(use_operand)
        elif use_math == "square_root":
            result = f_before ** 0.5
    except (ValueError, ZeroDivisionError, OverflowError):
        e.insert(0, "Error")
        history_var.set("")
        running_expr = ""
        after_equal = False
        new_number = True
        return

    if result is not None:
        result    = smart_round(result)
        sym       = op_symbols.get(use_math, "?")
        op_clean  = _clean_num_str(str(smart_round(use_operand)))
        f_clean   = smart_round(f_before)

        if after_equal:
            # Repeat-= history: show "{prev_result} {op} {operand} ="
            history_var.set(f"{f_clean} {sym} {op_clean} =")
        else:
            # Normal history: append second operand to running expression
            history_var.set(f"{running_expr}{op_clean} =")
            running_expr = ""   # reset for next fresh calculation

        f_num        = result        # update so next repeat-= uses this result
        last_operand = use_operand   # remember for repeat-=
        last_math_op = use_math      # remember for repeat-=
        after_equal  = True          # next = press will repeat
        e.insert(0, result)
    new_number = True

# function to add
def button_add():
    global f_num, math, new_number, running_expr
    prev = _clean_num_str(e.get()) if e.get() else "0"
    _chain_compute()
    first_number = _get_and_clean()
    if not first_number: return
    math = "addition"
    f_num = float(first_number)
    running_expr += f"{prev} + "
    history_var.set(running_expr.rstrip())
    new_number = True


# function to subtract
def button_sub():
    global f_num, math, new_number, running_expr
    prev = _clean_num_str(e.get()) if e.get() else "0"
    _chain_compute()
    first_number = _get_and_clean()
    if not first_number: return
    math = "subtraction"
    f_num = float(first_number)
    running_expr += f"{prev} - "
    history_var.set(running_expr.rstrip())
    new_number = True

# function to multiply
def button_mul():
    global f_num, math, new_number, running_expr
    prev = _clean_num_str(e.get()) if e.get() else "0"
    _chain_compute()
    first_number = _get_and_clean()
    if not first_number: return
    math = "multiplication"
    f_num = float(first_number)
    running_expr += f"{prev} × "
    history_var.set(running_expr.rstrip())
    new_number = True


# function to divide
def button_div():
    global f_num, math, new_number, running_expr
    prev = _clean_num_str(e.get()) if e.get() else "0"
    _chain_compute()
    first_number = _get_and_clean()
    if not first_number: return
    math = "division"
    f_num = float(first_number)
    running_expr += f"{prev} ÷ "
    history_var.set(running_expr.rstrip())
    new_number = True

# function to calculate power
def button_pow():
    global f_num, math, new_number, running_expr
    prev = _clean_num_str(e.get()) if e.get() else "0"
    _chain_compute()
    first_number = _get_and_clean()
    if not first_number: return
    math = "power"
    f_num = float(first_number)
    running_expr += f"{prev} ^ "
    history_var.set(running_expr.rstrip())
    new_number = True

# function to calculate square root
def button_sqrt():
    global f_num, math, new_number, running_expr
    prev = _clean_num_str(e.get()) if e.get() else "0"
    _chain_compute()
    first_number = _get_and_clean()
    if not first_number: return
    math = "square_root"
    f_num = float(first_number)
    running_expr += f"√{prev} "
    history_var.set(running_expr.rstrip())
    new_number = True

# function to calculate modulo
def button_mod():
    global f_num, math, new_number, running_expr
    prev = _clean_num_str(e.get()) if e.get() else "0"
    _chain_compute()
    first_number = _get_and_clean()
    if not first_number: return
    math = "modulo"
    f_num = float(first_number)
    running_expr += f"{prev} % "
    history_var.set(running_expr.rstrip())
    new_number = True

# function to delete last number
def button_bacsp():
    global f_num, math, new_number, running_expr, last_operand, last_math_op, after_equal
    current = e.get()
    new_val = current[:-1]
    e.delete(0, END)
    if new_val == "" or new_val == "-":
        e.insert(0, "0")
        # Full state reset so stale running_expr doesn't pollute next operator press
        history_var.set("")
        f_num = 0.0
        math = ""
        new_number = False
        running_expr = ""
        last_operand = None
        last_math_op = ""
        after_equal = False
    else:
        e.insert(0, new_val)



# button configuration 
# number(0-9) and period(.) symbol
b1=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="1",font=('Arial', 18),width=33,height=40, command= lambda: b_click(1))
b2=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="2",font=('Arial', 18),width=33,height=40, command= lambda: b_click(2))
b3=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="3",font=('Arial', 18),width=33,height=40, command= lambda: b_click(3))
b4=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="4",font=('Arial', 18),width=33,height=40, command= lambda: b_click(4))
b5=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="5",font=('Arial', 18),width=33,height=40, command= lambda: b_click(5))
b6=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="6",font=('Arial', 18),width=33,height=40, command= lambda: b_click(6))
b7=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="7",font=('Arial', 18),width=33,height=40, command= lambda: b_click(7))
b8=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="8",font=('Arial', 18),width=33,height=40, command= lambda: b_click(8))
b9=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="9",font=('Arial', 18),width=33,height=40, command= lambda: b_click(9))
b0=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text="0",font=('Arial', 18),width=33,height=40, command= lambda: b_click(0))
b_dot=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#647a6d",fg_color="#9bb8a7",text_color="black",text=".",font=('Arial', 18),width=33,height=40, command= lambda: b_click('.'))

# Button operators 
b_sqrt=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="√",font=('Arial', 18),width=33,height=40, command=button_sqrt)
b_pow=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="^",font=('Arial', 18),width=33,height=40, command=button_pow)
b_mul=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="*",font=('Arial', 18),width=33,height=40,command=button_mul)
b_div=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="/",font=('Arial', 18),width=33,height=40, command=button_div)
b_sub=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="-",font=('Arial', 18),width=33,height=40, command=button_sub)
b_add=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="+",font=('Arial', 18),width=33,height=40,command=button_add)
b_equal=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="=",font=('Arial', 18),width=33,height=40,command=button_equal)
b_clear=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#ff5b5b",fg_color="#ff8686",text_color="black",text="AC",font=('Arial', 18),width=33,height=40,command= button_clear)
b_mod=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="%",font=('Arial', 18),width=33,height=40, command=button_mod)
b_bacsp=ctk.CTkButton(root,border_width=0,corner_radius=22,hover_color="#25b05f",fg_color="#78ffb0",text_color="black",text="⌫",font=('Arial', 18),width=33,height=40, command=button_bacsp)

# Make all 4 columns equal width and all button rows equal height
for col in range(4):
    root.columnconfigure(col, weight=1, uniform="btn")
for row in range(2, 8):   # rows 2-7 are button rows
    root.rowconfigure(row, weight=1, uniform="btn")

# Button placement
b1.grid(row=3,column=0, sticky="nsew", padx=5, pady=5)
b2.grid(row=3,column=1, sticky="nsew", padx=5, pady=5)
b3.grid(row=3,column=2, sticky="nsew", padx=5, pady=5)
b4.grid(row=4,column=0, sticky="nsew", padx=5, pady=5)
b5.grid(row=4,column=1, sticky="nsew", padx=5, pady=5)
b6.grid(row=4,column=2, sticky="nsew", padx=5, pady=5)
b7.grid(row=5,column=0, sticky="nsew", padx=5, pady=5)
b8.grid(row=5,column=1, sticky="nsew", padx=5, pady=5)
b9.grid(row=5,column=2, sticky="nsew", padx=5, pady=5)
b0.grid(row=6,column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
b_dot.grid(row=6,column=2, sticky="nsew", padx=5, pady=5)

b_add.grid(row=4,column=3,sticky="nsew", padx=5, pady=5)
b_equal.grid(row=7,column=0, columnspan=3,sticky="nsew",  padx=5, pady=5)
b_clear.grid(row=2,column=3,sticky="nsew",  padx=5, pady=5)
b_mul.grid(row=6,column=3,sticky="nsew",  padx=5, pady=5)
b_div.grid(row=7,column=3,sticky="nsew", padx=5, pady=5)
b_sub.grid(row=5,column=3,sticky="nsew",  padx=5, pady=5)
b_pow.grid(row=2,column=2,sticky="nsew",  padx=5, pady=5)
b_sqrt.grid(row=2,column=1,sticky="nsew",  padx=5, pady=5)
b_mod.grid(row=2,column=0,sticky="nsew",  padx=5, pady=5)
b_bacsp.grid(row=3,column=3,sticky="nsew",  padx=5, pady=5)

# Keyboard bindings — work immediately on launch without clicking entry
def handle_key(event):
    key = event.char
    keysym = event.keysym
    if key in ('0','1','2','3','4','5','6','7','8','9'): 
        b_click(key)
    elif key == '.':
        b_click('.')
    elif key == '+':
        button_add()
    elif key == '-':
        button_sub()
    elif key == '*':
        button_mul()
    elif key == '/':
        button_div()
    elif key == '^':
        button_pow()
    elif key == '%':
        button_mod()
    elif keysym in ('Return', 'KP_Enter', 'equal'):
        button_equal()
    elif keysym == 'BackSpace':
        button_bacsp()
    elif keysym == 'Escape':
        button_clear()

root.bind('<Key>', handle_key)
root.focus_set()

root.mainloop()
