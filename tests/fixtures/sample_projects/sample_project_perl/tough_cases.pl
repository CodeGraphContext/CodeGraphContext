#!/usr/bin/perl
use strict;
use warnings;

# Tough Case 1: Package-based OOP with Bless
# This is the standard but extremely manual way to do objects in Perl.
package Animal;
sub new {
    my ($class, $name) = @_;
    my $self = { name => $name };
    return bless $self, $class;
}

sub speak {
    my $self = shift;
    return "The " . $self->{name} . " makes a sound";
}

package Dog;
our @ISA = qw(Animal); # Inheritance via @ISA array

sub speak {
    my $self = shift;
    return $self->SUPER::speak() . "... Woof!";
}

# Tough Case 2: Reference-based Callbacks
my $callback = sub {
    my ($msg) = @_;
    print "Callback: $msg\n";
};

sub execute_callback {
    my ($cb, $val) = @_;
    $cb->($val);
}

execute_callback($callback, "Hello from Perl");

# Tough Case 3: Dynamic Subroutine Access
# Using the symbol table to call a function.
sub hidden_gem {
    return "Found a gem!";
}

my $func_name = "hidden_gem";
{
    no strict 'refs';
    print &$func_name();
}

# Tough Case 4: Module Exporting
package MyExporter;
use Exporter 'import';
our @EXPORT = qw(exported_func);

sub exported_func {
    return "I am exported";
}

1;
