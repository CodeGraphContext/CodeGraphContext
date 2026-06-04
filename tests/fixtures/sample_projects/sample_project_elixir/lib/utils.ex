defmodule MyApp.Utils do
  def format_data(data) do
    "Formatted: #{inspect(data)}"
  end

  defmacro log_execution(block) do
    quote do
      require Logger
      Logger.info("Starting execution")
      result = unquote(block)
      Logger.info("Finished execution")
      result
    end
  end
end
