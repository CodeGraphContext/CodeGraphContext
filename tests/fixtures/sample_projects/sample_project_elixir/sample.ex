defmodule MyApp.Worker do
  use GenServer
  alias MyApp.Repo
  import Ecto.Query
  require Logger

  @behaviour MyApp.WorkerBehaviour

  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  defp do_work(state) do
    Logger.info("working")
    Repo.all(from(u in User, where: u.active))
  end

  defmacro my_macro(expr) do
    quote do
      unquote(expr)
    end
  end

  def handle_call(:get, _from, state) do
    {:reply, state, state}
  end
end

defprotocol MyApp.Serializable do
  def serialize(data)
end

defimpl MyApp.Serializable, for: Map do
  def serialize(data), do: Jason.encode!(data)
end
