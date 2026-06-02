import signal
import sys
import logging

class ShutdownManager:
    def __init__(self) -> None:
        self.stop_requested: bool = False
        self._logger = logging.getLogger(__name__)
        
        # Register the SIGINT (Ctrl-C) signal handler
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum: int, frame) -> None:
        if not self.stop_requested:
            # --- FIRST CTRL-C ---
            self._logger.warning("[Ctrl-C] First press detected. Requesting graceful shutdown...")
            print("\n[INFO] Graceful shutdown initiated. The scheduler will stop after the current task completes.")
            
            # Flip the flag for the scheduler loop
            self.stop_requested = True
            
            # Restore default behavior (SIG_DFL) for any subsequent Ctrl-C inputs
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        else:
            # --- SECOND CTRL-C (Fallback protection) ---
            print("\n[WARNING] Second Ctrl-C detected! Force quitting immediately.")
            sys.exit(1)
