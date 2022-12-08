from time import sleep, time

from PyQt5.QtCore import QRunnable, pyqtSlot

from gui.events.state_change_events import SetTipTextEvent, InjectTextEvent
from gui.events.utils import eventbus
from gui.events.utils.eventbus import subscribe
from gui.events.utils.threadpool import threadpool

DELAY_SECS = 15


class TipRefresherService(QRunnable):
    TIPS = {
        "Tip: You can use Ctrl/Alt + 1/2/3/... in the quicksearch bar to quickly send cards to the simulator.",
        "Tip: Select a unit then press Ctrl + D or Ctrl + Shift + D to clone it.",
        "Tip: Hover on an option if you don't know what it does.",
        "Tip: Importing cards from game ID uses SSR posters to detect what cards you have.",
        "Tip: Use the \"Partial match\" option. It's fairly good, I think.",
        "Tip: Right clicking the song list will toggle between note type count and note type percentage.",
        "Tip: Right clicking the song list with Shift pressed"
        " will toggle between note type count and note type percentage.",
        "Tip: Leftmost red square = Center, rightmost blue square = Guest.",
        "Tip: For idol position, 1 2 3 4 5 in unit storage and calculator will be 4 2 1 3 5 in the actual game.",
        "Tip: You can drag the chart up and down in the chart viewer. Just do it like you would on a smartphone.",
        "Tip: You can click notes and skills on the chart viewer to see details about them.",
        "Tip: You can see detailed information of notes and skills at Chart viewer Perfect mode after simulation.",
        "Tip: If you need abuse chart, use Chart viewer Abuse mode.",
        "Tip: Chart viewer Custom mode allows you to set skill deactivation and note offset.",
        "Tip: Press Ctrl + F from anywhere to quickly jump to the search bar.",
        "Tip: Press Ctrl + Shift + F from anywhere to quickly jump to the song search bar.",
        "Tip: Press Ctrl + Shift + Q/W/E/R in the quicksearch bar to toggle the 4 options (except carnival cards).",
        "Tip: Press Ctrl + Shift + H from anywhere to hide/unhide the unit locking options,"
        " making the calculator view more compact.",
        "Tip: If you see some discrepancy between Chihiro and Dereguide2,"
        " it is because Dereguide2 likely uses [ ] skill boundary while Chihiro uses ( ] by default.",
        "Tip: Drag and drop a song into an unit while it's chart locked to quickly change the chart.",
        "Tip: You can use Custom Card to simulate My Style Card, and cards that doesn't exist in the game."
    }

    def __init__(self):
        super().__init__()
        self.current_tip = None
        self.scheduled_time = time()
        self.running = True
        self.current_tips = self.TIPS.copy()
        eventbus.eventbus.register(self)

    @pyqtSlot()
    def run(self):
        self.set_timer(10)
        eventbus.eventbus.post(SetTipTextEvent("You can see various tips on how to use the tool here."))
        self.schedule_tip_display()

    def schedule_tip_display(self):
        while self.running:
            sleep(0.2)
            if time() >= self.scheduled_time:
                self.select_next_tip()
                self.send_to_view()
                self.set_timer(DELAY_SECS)

    def select_next_tip(self):
        if len(self.current_tips) == 0:
            self.current_tips = self.TIPS.copy()
        self.current_tip = self.current_tips.pop()

    def send_to_view(self):
        eventbus.eventbus.post(SetTipTextEvent(self.current_tip))

    def set_timer(self, offset: int):
        self.scheduled_time = time() + offset

    def disable(self):
        self.running = False

    @subscribe(InjectTextEvent)
    def inject_message(self, event: InjectTextEvent):
        self.set_timer(event.offset)
        eventbus.eventbus.post(SetTipTextEvent(event.text))


__service = TipRefresherService()


def start_tip_refresher_service():
    threadpool.start(__service)


def kill_tip_refresher_service():
    __service.disable()
