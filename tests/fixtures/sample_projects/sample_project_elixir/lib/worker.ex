defmodule MyApp.Worker do
  use GenServer
  require Logger
  alias MyApp.Utils

  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  def init(state) do
    {:ok, state}
  end

  def handle_call(:process, _from, state) do
    result = Utils.format_data(state)
    {:reply, result, state}
  end
end
