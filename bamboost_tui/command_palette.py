from __future__ import annotations

from time import monotonic

from textual import work
from textual.binding import Binding
from textual.command import Command, CommandList
from textual.command import CommandPalette as BaseCommandPalette
from textual.worker import get_current_worker


class CommandPalette(BaseCommandPalette):
    BINDINGS = [
        Binding("ctrl+n", "cursor_down", "move cursor down", show=False),
        Binding("ctrl+p", "command_list('cursor_up')", "move cursor up", show=False),
    ]

    @work(exclusive=True, group=BaseCommandPalette._GATHER_COMMANDS_GROUP)
    async def _gather_commands(self, search_value: str) -> None:
        """Gather up all of the commands that match the search value.

        Args:
            search_value: The value to search for.
        """
        gathered_commands: list[Command] = []
        command_list = self.query_one(CommandList)
        if (
            command_list.option_count == 1
            and command_list.get_option_at_index(0).id == self._NO_MATCHES
        ):
            command_list.remove_option(self._NO_MATCHES)

        command_id = 0
        worker = get_current_worker()

        # Reset busy mode.
        self._show_busy = False
        clear_current = True
        last_update = monotonic()

        # Kick off the search, grabbing the iterator.
        search_routine = self._search_for(search_value)
        search_results = search_routine.__aiter__()

        # We're going to be doing the send/await dance in this code, so we
        # need to grab the first yielded command to start things off.
        try:
            hit = await search_results.__anext__()
        except StopAsyncIteration:
            hit = None

        while hit:
            # NEEDED TO CHANGE THIS LINE. RENDER THE PROMPT DIRECTLY
            prompt = hit.prompt

            gathered_commands.append(Command(prompt, hit, id=str(command_id)))

            if worker.is_cancelled:
                break

            now = monotonic()
            if (now - last_update) > self._RESULT_BATCH_TIME:
                self._refresh_command_list(
                    command_list, gathered_commands, clear_current
                )
                clear_current = False
                last_update = now

            command_id += 1

            try:
                hit = await search_routine.asend(worker.is_cancelled)
            except StopAsyncIteration:
                break

        if not worker.is_cancelled:
            self._refresh_command_list(command_list, gathered_commands, clear_current)

        # One way or another, we're not busy any more.
        self._show_busy = False

        if command_list.option_count == 0 and not worker.is_cancelled:
            self._hit_count = 0
            self._start_no_matches_countdown(search_value)

        self.add_class("-ready")
