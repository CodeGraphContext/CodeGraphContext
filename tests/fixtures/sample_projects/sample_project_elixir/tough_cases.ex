defmodule Tough.Cases do
  @moduledoc """
  Tough Case 1: Macros (defmacro)
  Generating functions at compile-time.
  """
  defmacro __using__(_opts) do
    quote do
      def identity, do: __MODULE__
      
      def log(msg) do
        IO.puts("[#{__MODULE__}] #{msg}")
      end
    end
  end
end

defmodule Tough.Worker do
  use Tough.Cases # This should inject 'identity' and 'log'

  def perform do
    log("Starting work") # Should link to injected macro function
    IO.puts("Identity: #{identity()}")
  end
end

defmodule Tough.Protocol do
  @doc """
  Tough Case 2: Protocols and Implementations
  """
  defprotocol Shippable do
    def ship(item, destination)
  end

  defmodule Package do
    defstruct [:id, :weight]
  end

  defimpl Shippable, for: Package do
    def ship(package, dest) do
      "Shipping package #{package.id} to #{dest}"
    end
  end
end
