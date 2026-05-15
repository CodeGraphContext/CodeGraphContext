defmodule MyApp.Main do
  alias MyApp.Worker
  alias MyApp.Utils
  alias MyApp.Serializable

  require Utils

  def run do
    Utils.log_execution do
      {:ok, pid} = Worker.start_link(%{initial: "state"})
      result = GenServer.call(pid, :process)
      IO.puts("Worker result: #{result}")

      data = %{key: "value"}
      IO.puts("Serialized: #{Serializable.serialize(data)}")
    end
  end
end
