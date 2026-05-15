package MyModule::Shapes;
use strict;
use warnings;

sub new {
    my ($class, %args) = @_;
    return bless \%args, $class;
}

sub area {
    die "Subclass must implement area";
}

1;
