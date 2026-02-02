from pynput import keyboard


class KeyboardController:
    def __init__(self):
        self.go_flag = 0
        self.left_flag = 0
        self.right_flag = 0
        self.back_flag = 0
        self.brake_flag = 0
        self.parking_flag = 0
        self.save_flag = 0
        self.exit_flag = 0
        self.manual = 1

    def getkeyboard(self):
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()

    # 키보드 눌릴 때 실행
    def on_press(self, key):
        try:
            if key == keyboard.Key.esc:
                print('Exit is pressed')
                self.exit_flag=1
                return False
            if key == keyboard.Key.up:
                self.go_flag=1
            if key == keyboard.Key.left:
                self.left_flag=1
            if key == keyboard.Key.right:
                self.right_flag=1
            if key == keyboard.Key.down:
                self.back_flag=1
        except:
            pass

        try:
            if key.char.lower() == 'b':
                self.brake_flag=1
            if key.char.lower() == 'p':
                self.parking_flag=1
            if key.char.lower() == 'g':
                self.save_flag=1
                print('Save mode ON')
            if key.char.lower() == 'f':
                self.save_flag=0
                print('Save mode OFF')
            if key.char.lower() == 'z':
                self.manual = 0
                print('Autonomous mode ON')
            if key.char.lower() == 'x':
                self.manual = 1
                self.go_flag = 0
                self.left_flag=0
                self.right_flag=0
                print('Autonomous mode OFF')
            # print('on', self.go_flag, self.left_flag, self.right_flag, self.back_flag,
            #       self.brake_flag, self.save_flag, self.exit_flag, self.manual)
        except:
            pass

    # 키보드 뗄 때 실행
    def on_release(self, key):
        try:
            if key == keyboard.Key.up:
                self.go_flag=0
            if key == keyboard.Key.left:
                self.left_flag=0
            if key == keyboard.Key.right:
                self.right_flag=0
            if key == keyboard.Key.down:
                self.back_flag=0
        except:
            pass

        try:
            if key.char.lower() == 'b':
                self.brake_flag=0
            if key.char.lower() == 'p':
                self.parking_flag=0
            # print('off', self.go_flag, self.left_flag, self.right_flag, self.back_flag,
            #       self.brake_flag, self.save_flag, self.exit_flag, self.manual)
        except:
            pass



if __name__ == "__main__":
    import threading
    k = KeyboardController()
    getkey_thread = threading.Thread(target=k.getkeyboard)
    getkey_thread.start()

