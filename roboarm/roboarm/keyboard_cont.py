from pynput import keyboard


class KeyboardController:
    def __init__(self):
        self.save_flag = 0
        self.exit_flag = 0
        self.servo_channel = -1
        self.servo_direction = 0

    def getkeyboard(self):
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()

    # 키보드 눌릴 때 실행
    def on_press(self, key):
        try:
            if key == keyboard.Key.esc:
                print('Exit is pressed')
                self.exit_flag = 1
                return False
        except:
            pass

        try:
            if key.char.lower() == 'g':
                self.save_flag = 1
                print('Save mode ON')
            if key.char.lower() == 'h':
                self.save_flag = 0
                print('Save mode OFF')
            # 서보 제어 키 (플래그 방식)
            # Q/A: Base(0), W/S: Shoulder(1), E/D: Elbow(2), R/F: Gripper(3)
            servo_map = {'q':(0,1),'a':(0,-1),'w':(1,1),'s':(1,-1),'e':(2,1),'d':(2,-1),'r':(3,1),'f':(3,-1)}
            if key.char.lower() in servo_map:
                ch, dr = servo_map[key.char.lower()]
                self.servo_channel = ch
                self.servo_direction = dr
        except:
            pass

    # 키보드 뗄 때 실행
    def on_release(self, key):
        try:
            if key.char.lower() in ('q','a','w','s','e','d','r','f'):
                self.servo_channel = -1
                self.servo_direction = 0
        except:
            pass


if __name__ == "__main__":
    import threading
    k = KeyboardController()
    getkey_thread = threading.Thread(target=k.getkeyboard)
    getkey_thread.start()
